"""Stablecoin Stress Lab: observed evidence → liquidity experiments → validation."""
import csv
import io
import json
import time
from datetime import datetime, timezone
from threading import BoundedSemaphore
import altair as alt
import pandas as pd
import streamlit as st
from research_data import (ROOT,TOKEN_COLORS,CASES,load_research,latest_market,saved_report,event_frames,snapshot_detail)
from backend.app.domain.schemas import PortfolioRequest, AgentExperimentRequest
from backend.app.domain.stable_swap import quote_swap
from backend.app.services.portfolio import portfolio_stress
from backend.app.services.agents import simulate_agents, phase_diagram

st.set_page_config(page_title='Stablecoin Stress Lab',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
:root{--ink:#132b3b;--muted:#647782;--teal:#087f78}
.stApp{background:#f6f8fa;color:var(--ink)}
.stMainBlockContainer{max-width:1320px;padding-top:2.4rem;padding-bottom:3rem}
h1,h2,h3{color:var(--ink);letter-spacing:-.035em}h1{font-weight:650!important;font-size:2.65rem!important;line-height:1.15!important}h2{font-size:1.6rem!important}h3{font-size:1.16rem!important}
.stMarkdown p{line-height:1.65}.stCaption{color:var(--muted)}
[data-testid="stSidebar"]{background:#112a3b;color:#edf4f7;border-right:0}
[data-testid="stSidebar"] *{color:inherit}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#a8c2cf}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:.4rem 0}
[data-testid="stMetric"]{background:white;border:1px solid #e0e8ed;border-radius:12px;padding:1.1rem 1.2rem}
[data-testid="stMetricLabel"]{color:#667b88;font-size:.83rem}
[data-testid="stMetricValue"]{font-size:1.85rem;font-weight:600;letter-spacing:-.03em}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-color:#e0e8ed!important;border-radius:12px}
[data-testid="stExpander"]{background:#fff;border-color:#e0e8ed!important}
.stButton>button[kind="primary"]{background:#087f78;border-color:#087f78;color:white;border-radius:8px}
.stButton>button{border-radius:8px}
.eyebrow{font-size:.73rem;letter-spacing:.16em;font-weight:700;color:#087f78;margin-bottom:12px;text-transform:uppercase}
.deck{color:#627684;font-size:1.06rem;max-width:850px;margin:8px 0 24px;line-height:1.6}
.data-strip{border-top:1px solid #dce5eb;border-bottom:1px solid #dce5eb;padding:11px 0;margin:0 0 25px;font-size:.78rem;color:#607481;line-height:1.9}
.brand{font-size:1.1rem;font-weight:650;letter-spacing:-.02em;margin:4px 0 5px}.brand-mark{color:#5bd3b7;font-size:1.6rem}
.sidebar-kicker{color:#8eafc0;font-size:.68rem;letter-spacing:.17em;margin-top:3px;margin-bottom:28px}
.card-label{font-size:.73rem;letter-spacing:.1em;color:#69818e;font-weight:650;text-transform:uppercase}
.badge{display:inline-block;background:#e1f2ed;color:#116855;padding:4px 10px;border-radius:20px;font-size:.73rem;font-weight:650}
.sidebar-footer{border-top:1px solid #2a4555;margin-top:28px;padding-top:18px;color:#a8c2cf;font-size:.75rem;line-height:1.9}
@media(max-width:700px){h1{font-size:2rem!important}.stMainBlockContainer{padding-top:1.2rem}[data-testid="stMetricValue"]{font-size:1.5rem}}
</style>''',unsafe_allow_html=True)
alt.theme.enable('default')

@st.cache_data
def research():
    return load_research()
@st.cache_resource
def slots():
    return BoundedSemaphore(2)
def calculate(fn,request):
    times=st.session_state.setdefault('calculations',[])
    now=time.monotonic();times[:]=[t for t in times if t>now-60]
    if len(times)>=12:raise ValueError('Please wait a moment. Each session can run 12 experiments per minute.')
    lock=slots()
    if not lock.acquire(False):raise ValueError('The research engine is busy. Please try again shortly.')
    try:
        times.append(now)
        return fn(request)
    finally:lock.release()

def route(page):
    st.session_state['workspace']=page

def open_sale(day):
    st.session_state['workspace']='Liquidity Stress Test'
    st.session_state['sale_date']=day

def header(kicker,title,description):
    st.markdown(f'<div class="eyebrow">{kicker}</div>',unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="deck">{description}</div>',unsafe_allow_html=True)

def strip(text):
    st.markdown(f'<div class="data-strip">{text}</div>',unsafe_allow_html=True)

def json_export(result,name,label='Download reproducible experiment'):
    st.download_button(label,json.dumps(result,indent=2,default=str),name,'application/json')

def price_chart(frame,height=280,bps=False):
    frame=frame.copy()
    frame['utc_date']=frame.date_utc.astype(str)
    frame['deviation_bps']=(frame.close_usd-1)*10000
    field='deviation_bps' if bps else 'close_usd'
    title='Deviation from USD 1 (bps)' if bps else 'USD price'
    x=alt.X('date_utc:T',title='Observation date (UTC)',scale=alt.Scale(type='utc'),axis=alt.Axis(format='%b %d',grid=False))
    curve=alt.Chart(frame).mark_line(strokeWidth=2.3).encode(x=x,y=alt.Y(field+':Q',title=title,scale=alt.Scale(zero=False)),color=alt.Color('asset:N',scale=alt.Scale(domain=['USDC','USDT'],range=[TOKEN_COLORS['USDC'],TOKEN_COLORS['USDT']]),legend=alt.Legend(title=None,orient='top')),tooltip=[alt.Tooltip('utc_date:N',title='UTC date'),'asset:N',alt.Tooltip('close_usd:Q',title='USD',format='.6f')])
    baseline=alt.Chart(pd.DataFrame({'reference':[0 if bps else 1]})).mark_rule(color='#98a6b0',strokeDash=[4,4]).encode(y='reference:Q')
    st.altair_chart((curve+baseline).properties(height=height),width='stretch')

def path_chart(rows,fields,title):
    frame=pd.DataFrame(rows).melt(id_vars=['hour'],value_vars=fields,var_name='series',value_name='value')
    chart=alt.Chart(frame).mark_line(strokeWidth=2.2).encode(x=alt.X('hour:Q',title='Simulation hour'),y=alt.Y('value:Q',title=title,scale=alt.Scale(zero=False)),color=alt.Color('series:N',legend=alt.Legend(title=None,orient='top')),tooltip=['hour:Q','series:N',alt.Tooltip('value:Q',format=',.4f')]).properties(height=280)
    st.altair_chart(chart,width='stretch')

history,prices,snapshots=research()
market_rows,market,market_date,market_age=latest_market(history)
available=sorted({s['timestamp'][:10] for s in snapshots})
SNAPSHOT_LABELS={'2023-03-11':'USDC stress case','2022-05-12':'USDT stress case','2022-11-09':'FTX stress case'}
PAGES=['Overview','Historical Research','Liquidity Stress Test','Models & Validation']
with st.sidebar:
    st.markdown('<div class="brand-mark">◈</div><div class="brand">Stablecoin Stress Lab</div><div class="sidebar-kicker">LIQUIDITY RESEARCH</div>',unsafe_allow_html=True)
    page=st.radio('Research workspace',PAGES,key='workspace',label_visibility='collapsed')
    st.caption('A focused workspace for understanding price dislocations and liquidity under stress.')
    st.markdown(f'<div class="sidebar-footer">USD observations<br><strong>{market_date} UTC</strong><br><br>Historical pool data<br><strong>Ethereum · Curve 3pool</strong><br><br>Research prototype<br>No trades or wallet connection</div>',unsafe_allow_html=True)


def overview():
    header('01 / Market context','Stablecoins under stress.','Understand the observations. Explore liquidity mechanisms. Test a clearly defined hypothesis.')
    strip(f"USD data: {market_date} UTC · {'Recent daily snapshot' if market_age<=2 else 'Historical snapshot — refresh required'} · CoinGecko · Latest completed UTC day, not a live trading feed")
    if market_age>2:st.warning(f'The saved market snapshot is {market_age} days old. Treat the figures below as historical context.')
    cols=st.columns(3)
    for asset,col in zip(['USDC','USDT'],cols[:2]):
        row=market[(market.asset==asset)&(market.date_utc==market_date)].iloc[-1]
        col.metric(asset+' / USD',f"{row.close_usd:.6f}",f"{(row.close_usd-1)*10000:+.2f} bps from USD 1",delta_color='off',help='Last sampled price in a completed UTC day. One basis point is 0.01 percentage point.')
    cols[2].metric('Historical pool snapshots',f'{len(snapshots)}',help='Sparse snapshots with block metadata; these are not a continuous liquidity feed.')
    cols[2].caption(f'{available[0]} → {available[-1]} UTC')
    st.write('')
    left,right=st.columns([1.65,1],gap='large')
    with left:
        st.subheader('The last 30 observed days')
        recent=market[market.date_utc.isin(sorted(market.date_utc.unique())[-30:])]
        price_chart(recent,bps=True)
        st.caption('A price near USD 1 does not establish that a large sale can execute near USD 1. Pool depth and token composition are a separate question.')
    with right:
        with st.container(border=True):
            st.markdown('<div class="card-label">Featured case study</div>',unsafe_allow_html=True)
            st.subheader('USDC · March 2023')
            st.write('Follow the observed price dislocation, inspect the recorded pool composition, then test the effect of a larger liquidity buffer.')
            st.button('Explore the historical evidence →',type='primary',on_click=route,args=('Historical Research',),width='stretch')
            st.caption('Recorded observations and hypothetical experiments remain separate throughout.')
        st.write('')
        st.button('Start with a simple sale estimate →',on_click=route,args=('Liquidity Stress Test',),width='stretch')
    st.divider()
    st.subheader('Daily research brief')
    report=saved_report()
    if report:
        facts=report['facts'];data_date=facts['assets'][0]['as_of']
        method='AI-generated commentary' if report.get('llm_status')=='Generated with Alibaba Qwen' else 'Statistical brief'
        st.caption(f"{method} · data as of {data_date} UTC · generated {facts['generated_at_utc'][:16].replace('T',' ')} UTC")
        report_age=(datetime.now(timezone.utc).date()-datetime.fromisoformat(data_date).date()).days
        if report_age>2:st.warning('The saved brief is stale. Use its observation date, not today’s date, when interpreting it.')
        if method=='Statistical brief':
            for a in facts['assets']:
                st.write(f"**{a['asset']}** was last sampled at **USD {a['latest_usd']:.6f}**, a deviation of **{a['deviation_bps']:+.2f} bps** from USD 1.")
            st.write('These are price observations, not evidence about issuer reserves or redemption capacity. Assess potential execution costs separately using a sourced pool snapshot.')
            st.caption('Generated from structured data using a fixed English template. No current-news or reserve analysis is included.')
        else:
            body=report['markdown']
            st.markdown(body.replace('$',r'\$'))
        with st.expander('Full English brief and source record'):
            # Operational diagnostics belong in validation, not the visitor's reading flow.
            body=report['markdown']
            lines=[line.split('LLM status:')[0] for line in body.splitlines()]
            st.markdown('\n'.join(lines).replace('$',r'\$'))
            st.download_button('Download English brief',report['markdown'],'stablecoin-daily-brief.md','text/markdown')
            json_export(facts,'daily-brief-facts.json','Download underlying facts')
    else:st.info('No saved brief is available yet. Market observations above remain available.')
    with st.container(border=True):
        st.subheader('New to the lab? Follow one question.')
        st.write('1. **Observe** a historical price dislocation.  2. **Inspect** the pool at a recorded block.  3. **Test** a sale and a liquidity assumption.  4. **Check** what the model has and has not validated.')


def historical():
    header('02 / Historical evidence','What happened during the stress?','Read the market evidence first. Historical observations describe an event; model estimates explain a possible execution mechanism.')
    case=st.selectbox('Case study',list(CASES),key='research_case')
    start,end,default_day,event_id=CASES[case]
    frame,pools,shares=event_frames(prices,snapshots,case)
    strip(f'Case window: {start} → {end} UTC · Daily USD samples + sparse Ethereum pool snapshots · No interpolation between pool observations')
    asset='USDC' if case.startswith('USDC') else 'USDT'
    observed=frame[frame.asset==asset]
    low=observed.loc[observed.min_sampled_usd.idxmin()]
    share=shares[shares.asset==asset]
    highest=share.loc[share.share_pct.idxmax()] if len(share) else None
    c1,c2,c3=st.columns(3)
    c1.metric('Lowest sampled '+asset+' / USD',f'{low.min_sampled_usd:.6f}')
    c1.caption(str(low.date_utc)+' UTC')
    c2.metric('Peak observed '+asset+' token share',f"{highest.share_pct:.1f}%" if highest is not None else 'Unavailable')
    c2.caption('Among the stored pool snapshots')
    c3.metric('Pool observations in this window',str(len(pools)))
    c3.caption('Actual recorded blocks')
    st.caption('The sampled low comes from hourly observations. The line below shows daily last samples, so its trough can differ. Pool shares measure token quantities, not dollar-valued reserves.')
    left,right=st.columns([1.25,1],gap='large')
    with left:
        st.subheader('01 · Observe the USD price')
        price_chart(frame,height=300)
    with right:
        st.subheader('02 · Inspect pool composition')
        chart=alt.Chart(shares).mark_bar(size=28).encode(x=alt.X('date_utc:O',title='Snapshot date (UTC)',axis=alt.Axis(labelAngle=-35)),y=alt.Y('share_pct:Q',stack='zero',title='Share of token quantities (%)'),color=alt.Color('asset:N',scale=alt.Scale(domain=['DAI','USDC','USDT'],range=[TOKEN_COLORS[a] for a in ['DAI','USDC','USDT']]),legend=alt.Legend(title=None,orient='top')),tooltip=['date_utc:N','asset:N',alt.Tooltip('share_pct:Q',format='.2f')]).properties(height=300)
        st.altair_chart(chart,width='stretch')
    st.subheader('03 · Connect the evidence to an experiment')
    with st.container(border=True):
        st.write('A larger balance of one token can change the exchange rate and the amount of another token available to sell into. To isolate pool depth, the experiment scales all three balances proportionally while holding composition, amplification and fees fixed.')
        choices=[s['timestamp'][:10] for s in pools]
        day=st.selectbox('Choose a recorded pool date',choices,index=choices.index(default_day) if default_day in choices else 0,key='case_snapshot')
        snapshot=next(s for s in pools if s['timestamp'].startswith(day))
        st.caption('Actual pool observation: '+snapshot['timestamp']+' · USD price samples are not synchronized to this block.')
        st.button('Test a sale at this snapshot →',type='primary',on_click=open_sale,args=(day,))
    st.divider()
    st.subheader('Event context & source trail')
    for event in history['events']:
        if event['event_id']==event_id:
            st.write('**'+event['summary']+'**')
            st.markdown(event['price_series_note'].replace('$',r'\$'))
            st.caption(event['interpretation_caveat'])
            for source in history['sources']:
                if source['event_id']==event_id:st.link_button('Read original source',source['source_url'])
    with st.expander('Inspect recorded observations & export'):
        st.write('Pool snapshots')
        st.dataframe(pd.DataFrame(pools),hide_index=True,width='stretch')
        st.write('Daily USD observations')
        st.dataframe(frame,hide_index=True,width='stretch')
        st.download_button('Download case price observations',frame.to_csv(index=False),'case-prices.csv','text/csv')
        st.download_button('Download case pool observations',pd.DataFrame(pools).to_csv(index=False),'case-pools.csv','text/csv')


def sale_experiment():
    st.subheader('If I sell, what might the pool return?')
    st.write('Choose a token, an amount and a recorded pool date. Compare the historical pool estimate with one explicit change: more liquidity.')
    with st.form('sale_form'):
        c1,c2,c3=st.columns([1,1,1.3])
        asset=c1.selectbox('1 · Token to sell',['USDC','USDT'],key='sale_asset')
        amount=c2.number_input('2 · Tokens to sell',min_value=1.,max_value=1e9,value=100_000.,step=10_000.,key='sale_amount')
        day=c3.selectbox('3 · Historical pool date',available,index=None if 'sale_date' in st.session_state else available.index('2023-03-11'),key='sale_date',format_func=lambda d:d+' · '+SNAPSHOT_LABELS[d] if d in SNAPSHOT_LABELS else d,help='A recorded historical pool state, not a forecast date. The March 2023 case is a useful starting point.')
        increase=st.select_slider('Hypothetical increase in all pool balances',[0,10,30,50,100],value=30,format_func=lambda v:f'+{v}%',key='sale_increase')
        submitted=st.form_submit_button('Compare execution estimates',type='primary')
    if submitted:
        st.session_state['sale_result']=calculate(run_sale,dict(asset=asset,amount=amount,day=day,increase=increase))
    saved=st.session_state.get('sale_result')
    if not saved:
        with st.container(border=True):
            st.write('**What you will get**')
            st.write('Estimated output tokens, average exchange rate, fee, and price impact for two versions of the same historical pool. This does not estimate the probability of a future loss.')
        return
    # A form keeps edits private until submit. The stored request labels every result.
    req=saved['request'];output='USDT' if req['asset']=='USDC' else 'USDC'
    strip(f"Submitted experiment: sell {req['amount']:,.0f} {req['asset']} → {output} · {req['day']} pool · hypothetical balances +{req['increase']}%")
    st.subheader('Estimated tokens received')
    a,b=st.columns(2)
    a.metric('Historical snapshot model',f"{saved['historical']['net_output']:,.2f} {output}")
    b.metric(f"Hypothetical +{req['increase']}% liquidity",f"{saved['counterfactual']['net_output']:,.2f} {output}")
    delta=saved['counterfactual']['net_output']-saved['historical']['net_output']
    st.write(f"**The liquidity assumption changes estimated proceeds by {delta:+,.2f} {output}.** Both estimates use the same model, token mix, amplification and fee; the second pool has proportionally larger balances.")
    table=[]
    for label,key in [('Historical pool model','historical'),('Hypothetical liquidity','counterfactual')]:
        r=saved[key]
        table.append({'Scenario':label,f'Net {output} received':r['net_output'],f'{output} per {req["asset"]} (net)':r['average_execution_price_net'],'Price impact, fee excluded (%)':r['price_impact_ex_fee_pct'],f'Fee ({output})':r['fee_amount']})
    st.dataframe(pd.DataFrame(table),hide_index=True,width='stretch')
    st.caption('Price impact compares this trade’s average gross exchange rate with the model’s small-trade marginal rate. It is different from deviation against USD 1. Fees are shown separately; gas is excluded.')
    chart=alt.Chart(pd.DataFrame(saved['sensitivity'])).mark_line(point=True,strokeWidth=2.2).encode(x=alt.X('liquidity_increase_pct:Q',title='Hypothetical increase in pool balances (%)'),y=alt.Y('impact_bps:Q',title='Price impact excluding fee (bps)',scale=alt.Scale(zero=False)),tooltip=['liquidity_increase_pct:Q',alt.Tooltip('impact_bps:Q',format='.3f')]).properties(height=250)
    st.subheader('Sensitivity to pool depth')
    st.altair_chart(chart,width='stretch')
    with st.expander('Snapshot, assumptions & reproducible export'):
        st.json(snapshot_detail(saved['snapshot']))
        st.write('Balances are supplied as token quantities. The floating-point model approximates Curve execution; integer contract rounding and block-specific exchange-rate adjustments are not reproduced exactly. This is not an executable quote.')
        json_export(saved,'liquidity-experiment.json')


def run_sale(request):
    snapshot=next(s for s in snapshots if s['timestamp'].startswith(request['day']))
    i,j=(1,2) if request['asset']=='USDC' else (2,1)
    before=quote_swap(snapshot,i,j,request['amount'])
    after=quote_swap(snapshot,i,j,request['amount'],1+request['increase']/100)
    sensitivity=[]
    for change in sorted({0,10,30,50,100,request['increase']}):
        r=quote_swap(snapshot,i,j,request['amount'],1+change/100)
        sensitivity.append(dict(liquidity_increase_pct=change,impact_bps=r['price_impact_ex_fee_pct']*100))
    return dict(request=request,snapshot=snapshot,historical=before,counterfactual=after,sensitivity=sensitivity,label='Historical model estimate vs hypothetical liquidity assumption')

PRESETS={
    'Reserve access disruption':dict(scenario='bank_freeze',panic_pct=70,cash_ratio_pct=10,issuer_delay_hours=24,frozen_reserve_pct=20,rate_shock_bps=0,lp_withdrawal_pct=10),
    'Redemption rush and liquidity exits':dict(scenario='run_lp',panic_pct=95,cash_ratio_pct=5,issuer_delay_hours=12,frozen_reserve_pct=0,rate_shock_bps=0,lp_withdrawal_pct=60),
    'Rate shock with liquidity exits':dict(scenario='rate_hike',panic_pct=50,cash_ratio_pct=10,issuer_delay_hours=6,frozen_reserve_pct=0,rate_shock_bps=300,lp_withdrawal_pct=20)}

def holdings_experiment():
    st.subheader('How could a hypothetical shock affect my holdings?')
    st.write('Start with your holdings and a preset. This model illustrates a mechanism; it does not assess issuer safety or predict your actual loss.')
    c1,c2=st.columns(2)
    usdc=c1.number_input('USDC held',min_value=0.,max_value=1e10,value=10_000.,step=1000.,key='hold_usdc')
    usdt=c2.number_input('USDT held',min_value=0.,max_value=1e10,value=10_000.,step=1000.,key='hold_usdt')
    preset=st.selectbox('Hypothetical scenario',list(PRESETS),key='hold_scenario')
    day=st.selectbox('Historical starting pool',available,index=available.index('2023-03-11'),key='hold_date')
    values=PRESETS[preset].copy()
    descriptions={
        'Reserve access disruption':'Assumes 20% frozen reserves, a 24-hour processing delay and 10% LP withdrawal. These are research inputs, not historical issuer measurements.',
        'Redemption rush and liquidity exits':'Assumes elevated holder panic, limited cash and 60% LP withdrawal. This is a constructed joint shock, not a measured probability.',
        'Rate shock with liquidity exits':'Assumes a 300 bps rate shock and 20% LP withdrawal. Rate losses only apply to the optional hypothetical Treasury-token comparison.'}
    st.caption(descriptions[preset])
    with st.expander('Adjust scenario assumptions'):
        a,b=st.columns(2)
        values['panic_pct']=a.slider('Holder panic assumption (%)',0,100,values['panic_pct'],key='panic_'+preset)
        values['cash_ratio_pct']=b.slider('Cash reserve assumption (%)',0,100,values['cash_ratio_pct'],key='cash_'+preset)
        values['issuer_delay_hours']=a.slider('Issuer processing delay (hours)',0,168,values['issuer_delay_hours'],key='delay_'+preset)
        values['lp_withdrawal_pct']=b.slider('Maximum LP withdrawal (%)',0,90,values['lp_withdrawal_pct'],key='lp_'+preset)
        values['frozen_reserve_pct']=a.slider('Frozen reserve assumption (%)',0,100,values['frozen_reserve_pct'],key='freeze_'+preset)
        values['rate_shock_bps']=b.slider('Rate shock (bps; Treasury comparison)',-2000,2000,values['rate_shock_bps'],step=50,key='rate_'+preset)
    req=PortfolioRequest(date=day,usdc_amount=usdc,usdt_amount=usdt,**values)
    if st.button('Run holdings scenario',type='primary'):
        with st.spinner('Running the explicit scenario…'):
            st.session_state['hold_result']=(req.model_dump(mode='json'),calculate(portfolio_stress,req))
    saved=st.session_state.get('hold_result')
    if not saved:return
    if saved[0]!=req.model_dump(mode='json'):
        st.info('Inputs changed. Run the scenario again to update the results.')
        return
    result=saved[1]
    strip(f"HYPOTHETICAL SCENARIO · Reference date {day} · {req.duration_hours} model hours · Independent token simulations")
    cols=st.columns(3)
    cols[0].metric('Historical reference value',f"USD {result['reference_portfolio_usd']:,.2f}")
    cols[1].metric('Maximum modeled mark loss',f"USD {result['maximum_mark_loss_vs_reference_usd']:,.2f}")
    cols[2].metric('Modeled peak-to-trough drop',f"USD {result['maximum_path_drawdown_usd']:,.2f}")
    st.write('**How to read this:** the loss figure compares the lowest modeled holdings value with the historical daily-price reference. It is a scenario result, not an expected loss, VaR or a realized loss.')
    path_chart(result['portfolio_path'],['modeled_portfolio_usd'],'Synthetic holdings value (USD)')
    st.caption('USDC and USDT are simulated independently on mirrored pool templates. This synthetic portfolio path does not estimate correlations or a jointly consistent market. Pool-block times differ from daily USD reference times.')
    with st.expander('Separate sale estimates at the original snapshot'):
        st.write('Each sale is a separate hypothetical trade on the original pool. These are not simultaneous liquidations or trades at the stressed trough. Do not add these differences to the modeled mark loss.')
        st.dataframe(pd.DataFrame(result['independent_sale_estimates']),hide_index=True,width='stretch')
    with st.expander('Hypothetical Treasury-token comparison'):
        st.caption('Different reserve structures under the same input scenario. This is uncalibrated and is not evidence of product superiority.')
        rows=[]
        for name,r in result['comparison'].items():
            rows += [dict(hour=step['hour'],series=name,value=step['pool_implied_usdc_usd_after_agents']) for step in r['steps']]
        st.altair_chart(alt.Chart(pd.DataFrame(rows)).mark_line().encode(x='hour:Q',y=alt.Y('value:Q',title='Modeled USD quote',scale=alt.Scale(zero=False)),color='series:N').properties(height=260),width='stretch')
    with st.expander('Complete assumptions, source metadata & export'):
        st.json(result['request']);st.json(snapshot_detail(result['snapshot']))
        st.write(result['interpretation'])
        json_export(result,'holdings-scenario.json')


def participant_experiment():
    st.caption('For research use. Participants are rule-based cohorts, not language-model agents. The model is uncalibrated.')
    c1,c2=st.columns(2)
    day=c1.selectbox('Starting pool date',available,index=available.index('2023-03-11'),key='abm_date')
    asset=c2.selectbox('Stressed token',['USDC','USDT'],key='abm_asset')
    pressure=c1.slider('Redemption pressure (% of assumed supply)',0.,50.,5.,step=1.,key='abm_pressure')
    depth=c2.slider('Initial pool depth multiplier',.1,5.,1.,step=.1,key='abm_depth')
    panic=c1.slider('Holder panic (%)',0.,100.,50.,step=5.,key='abm_panic')
    capital=c2.number_input('Arbitrage capital (USD)',0.,1e11,5e6,step=1e6,key='abm_capital')
    with st.expander('Issuer and liquidity frictions'):
        delay=st.slider('Issuer processing delay (hours)',0,168,6,key='abm_delay')
        withdrawal=st.slider('Maximum LP withdrawal (%)',0.,90.,0.,step=5.,key='abm_lp')
        cash=st.slider('Cash reserve ratio assumption (%)',0.,100.,10.,step=5.,key='abm_cash')
        treasury=st.checkbox('Enable hypothetical Treasury stress factors',key='abm_treasury')
        rate=st.slider('Treasury rate shock (bps)',-2000.,2000.,0.,step=100.,key='abm_rate')
        duration=st.slider('Treasury duration assumption (years)',0.,20.,.25,step=.25,key='abm_duration')
        frozen=st.slider('Frozen reserves (%)',0.,100.,0.,step=5.,key='abm_frozen')
    req=AgentExperimentRequest(date=day,stress_asset=asset,redemption_pressure_pct=pressure,pool_liquidity_multiplier=depth,holder_panic=panic,arbitrage_capital_usd=capital,issuer_delay_hours=delay,lp_max_withdrawal_pct=withdrawal,cash_reserve_ratio_pct=cash,treasury_protocol_mode=treasury,rate_shock_bps=rate,asset_duration_years=duration,frozen_reserve_pct=frozen)
    a,b=st.columns(2)
    if a.button('Run participant experiment'):
        with st.spinner('Running participant rules…'):
            st.session_state['abm_result']=(req.model_dump(mode='json'),calculate(simulate_agents,req))
    if b.button('Compare 42 pressure / depth combinations'):
        with st.spinner('Building sensitivity grid…'):
            st.session_state['abm_phase']=(req.model_dump(mode='json'),calculate(phase_diagram,req))
    saved=st.session_state.get('abm_result')
    if saved and saved[0]==req.model_dump(mode='json'):
        result=saved[1]
        path_chart(result['steps'],['pool_implied_usdc_usd_after_agents'],'Modeled stressed-token USD quote')
        with st.expander('Participant flows and model state'):
            path_chart(result['steps'],['dai_pool','usdc_pool','usdt_pool'],'Pool token quantities')
            st.json(result['summary']);st.json(req.model_dump(mode='json'))
        json_export(result,'participant-experiment.json')
    elif saved:st.info('Participant inputs changed. Run again to update this result.')
    phase=st.session_state.get('abm_phase')
    if phase and phase[0]==req.model_dump(mode='json'):
        frame=pd.DataFrame(phase[1]['cells'])
        st.altair_chart(alt.Chart(frame).mark_rect().encode(x=alt.X('redemption_pressure_pct:O',title='Redemption pressure (%)'),y=alt.Y('liquidity_multiplier:O',title='Pool depth multiplier',sort='descending'),color=alt.Color('max_move_from_initial_pct:Q',title='Max move from start (pp)'),tooltip=list(frame.columns)).properties(height=300),width='stretch')
        json_export(phase[1],'participant-sensitivity.json')


def stress_test():
    header('03 / Mechanism experiments','Liquidity stress experiments.','Start with a simple sale estimate or holdings scenario. Advanced participant rules are available when you need to inspect the mechanism.')
    strip('Historical starting conditions + hypothetical assumptions · Model outputs are estimates · No live quotes or trades')
    sale,holdings=st.tabs(['Sell a position','Stress my holdings'])
    with sale:sale_experiment()
    with holdings:holdings_experiment()
    st.divider()
    with st.expander('Advanced research · participant dynamics and sensitivity grid'):
        participant_experiment()


def validation():
    header('04 / Evidence standards','Know what the model can support.','Compare forecast baselines, inspect model assumptions and trace the underlying data. See which results have been checked and which remain research hypotheses.')
    forecast_tab,execution_tab,data_tab,roadmap_tab=st.tabs(['Forecast validation','Execution & scenario models','Data & provenance','Research roadmap'])
    with forecast_tab:
        from forecast_ui import render_forecast_research
        render_forecast_research(market_rows)
    with execution_tab:
        st.subheader('Validation status')
        table=[
            {'Component':'Curve execution model','Evidence available':'Historical balances, A, fee and block metadata; numerical consistency checks','What remains open':'Contract get_dy / realized-transaction benchmark, token-rate precision and integer rounding','Status':'Approximation'},
            {'Component':'Rule-based participant model','Evidence available':'Explicit cohort rules, reproducible parameters and sensitivity experiments','What remains open':'Calibration to observed trading/redemption flows and held-out event testing','Status':'Uncalibrated'},
            {'Component':'Holdings scenarios','Evidence available':'Independent token paths and separate original-pool sale estimates','What remains open':'Joint price dynamics, correlations and synchronized valuation','Status':'Synthetic scenario'},
            {'Component':'Daily English brief','Evidence available':'Saved structured facts and generation timestamp','What remains open':'Optional Qwen commentary requires working server credentials; text needs factual review','Status':'Template / optional LLM'},
        ]
        st.dataframe(pd.DataFrame(table),hide_index=True,width='stretch')
        st.subheader('What numerical checks establish')
        st.write('Tests check conservation through the gross-output invariant, fee arithmetic, scale consistency, and execution-cost sensitivity across trade sizes. Passing these checks does not establish agreement with the historical Curve contract or realized trades.')
        st.subheader('How the execution estimate works')
        st.write('The solver computes the three-token StableSwap invariant using recorded balances and amplification A, then solves for the output balance after the input sale. A proportional fee is deducted from gross output. Liquidity counterfactuals scale all balances while preserving composition, A and fees.')
        st.subheader('How the holdings scenario works')
        st.write('Finite holder selling, constrained arbitrage, issuer queues and optional liquidity withdrawals evolve in hourly steps. Inputs such as frozen reserves, cash ratios and issuer delays are assumptions. Independent USDC and USDT runs are combined into a synthetic holdings path; no joint market model is estimated.')
        st.caption('No calibrated probability of safety, personal redemption ETA, statistical VaR or execution guarantee is produced.')
    with data_tab:
        st.subheader('Three different clocks')
        st.dataframe(pd.DataFrame([
            {'Dataset':'Recent USD prices','Clock':market_date+' UTC','Source':'CoinGecko market_chart','Meaning':'Last sampled observation in each completed UTC day'},
            {'Dataset':'Historical USD prices','Clock':str(prices.date_utc.min())+' → '+str(prices.date_utc.max()),'Source':'DefiLlama / underlying CoinGecko identifiers','Meaning':'Hourly samples aggregated by UTC day; not exchange OHLC'},
            {'Dataset':'Historical pool snapshots','Clock':available[0]+' → '+available[-1],'Source':'Ethereum JSON-RPC · Curve 3pool','Meaning':'Sparse exact-block state; missing dates are not interpolated'}
        ]),hide_index=True,width='stretch')
        st.write('USD prices and pool balances are not synchronized. Token balance totals must not be presented as dollar-valued reserves. Pool swap rates describe relative exchange rates; USD depeg measurement uses an independent USD series.')
        report=saved_report()
        if report:
            with st.expander('Daily brief generation record'):
                st.write('Generated (UTC): '+report['facts']['generated_at_utc'])
                st.write('LLM status: '+report.get('llm_status','Not recorded'))
                st.write('Scheduled for 09:15 Asia/Shanghai through GitHub Actions. Schedules can be delayed; failed market-data updates retain the previous dated report.')
        for name in ['data/manifest.json','data/processed/curve_3pool_manifest.json']:
            file=ROOT/name
            if file.exists():
                with st.expander('Inspect '+name):
                    st.json(json.loads(file.read_text()))
        st.link_button('Curve 3pool contract','https://etherscan.io/address/0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7#code')
    with roadmap_tab:
        st.subheader('Next evidence to earn')
        st.write('**1 · Execution accuracy.** Compare model outputs with archived contract get_dy calls at the same block, amount and token direction. Publish an error table rather than assuming historical accuracy.')
        st.write('**2 · Event calibration.** Fit participant parameters to observed flows, then evaluate on complete held-out stress events. Report sensitivity and failure cases.')
        st.write('**3 · Forecast robustness.** Add event-level holdouts, interval coverage, stress-regime errors and multiple seeds before claiming predictive value.')
        st.write('**4 · Representation learning.** JEPA remains a proposed experiment. Compare persistence, a supervised backbone and the same backbone with pretraining on chronological splits. No JEPA model is trained or deployed here.')
        st.caption('This roadmap describes future research, not current capabilities.')

try:
    {'Overview':overview,'Historical Research':historical,'Liquidity Stress Test':stress_test,'Models & Validation':validation}[page]()
except (ValueError,LookupError,KeyError,OSError) as exc:
    st.error('This analysis could not be completed. Check the selected data and inputs.')
    with st.expander('Analysis details'):st.write(str(exc))
st.divider()
st.caption('Stablecoin Stress Lab · Observed evidence, explicit assumptions, reproducible experiments. Research estimates do not establish future performance.')
