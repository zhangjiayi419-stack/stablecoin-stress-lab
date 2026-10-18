"""Stablecoin Stress Lab: observed evidence → liquidity experiments → validation."""
import csv
import io
import json
import time
from datetime import datetime, timezone
from threading import BoundedSemaphore
import plotly.graph_objects as go
from terminal_charts import show as show_chart, lines as line_chart
import pandas as pd
import streamlit as st
from research_data import (ROOT,TOKEN_COLORS,CASES,load_research,latest_market,saved_report,event_frames,snapshot_detail)
from backend.app.domain.schemas import PortfolioRequest, AgentExperimentRequest
from backend.app.domain.stable_swap import quote_swap
from backend.app.services.portfolio import portfolio_stress
from backend.app.services.agents import simulate_agents, phase_diagram

st.set_page_config(page_title='Stablecoin Stress Lab',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
from terminal_theme import install_terminal_theme
install_terminal_theme()
# Restore widget inputs before Streamlit reconstructs page-local controls.
for _key,_value in st.session_state.get('_retained_inputs',{}).items():
    if _key!='model_csv' and _key not in st.session_state:st.session_state[_key]=_value

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
        result=fn(request)
        from experiment_journal import record
        submitted=request.model_dump(mode='json') if hasattr(request,'model_dump') else request
        record(fn.__name__.replace('_',' ').title(),submitted,result)
        return result
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
    frame['deviation_bps']=(frame.close_usd-1)*10000
    field='deviation_bps' if bps else 'close_usd'
    fig=go.Figure()
    for asset,g in frame.groupby('asset',sort=False):
        fig.add_trace(go.Scatter(x=g.date_utc,y=g[field],name=asset,mode='lines',line=dict(color=TOKEN_COLORS[asset],width=2.3)))
    fig.add_hline(y=0 if bps else 1,line_dash='dash',line_color='#788da7')
    if bps:
        fig.add_hrect(y0=-4,y1=4,fillcolor='rgba(112,183,255,.07)',line_width=0)
        for bound in [-4,4]:fig.add_hline(y=bound,line_dash='dot',line_color='#526b85')
    fig.update_layout(xaxis_title='Observation date (UTC)',yaxis_title='Deviation from USD 1 (bps)' if bps else 'USD price')
    fig.update_yaxes(tickformat='.2f' if bps else '.4f')
    show_chart(fig,height)

def path_chart(rows,fields,title):
    line_chart(pd.DataFrame(rows),'hour',fields,title,'Simulation hour',height=280)

history,prices,snapshots=research()
market_rows,market,market_date,market_age=latest_market(history)
available=sorted({s['timestamp'][:10] for s in snapshots})
SNAPSHOT_LABELS={'2023-03-11':'USDC stress case','2022-05-12':'USDT stress case','2022-11-09':'FTX stress case'}
PAGES=['Overview','Daily Brief','Forecast Lab','Historical Research','Liquidity Stress Test','Mechanism Lab','Data & Contract Evidence','Experiment Journal','Models & Validation']
with st.sidebar:
    st.markdown('<div class="brand-mark">◈</div><div class="brand">Stablecoin Stress Lab</div><div class="sidebar-kicker">LIQUIDITY RESEARCH</div>',unsafe_allow_html=True)
    page=st.radio('Research workspace',PAGES,key='workspace',label_visibility='collapsed')
    st.caption('A focused workspace for understanding price dislocations and liquidity under stress.')
    st.markdown(f'<div class="sidebar-footer">USD observations<br><strong>{market_date} UTC</strong><br><br>Historical pool data<br><strong>Ethereum · Curve 3pool</strong><br><br>Research prototype<br>No trades or wallet connection</div>',unsafe_allow_html=True)


def overview():
    from home_ui import render_cover
    render_cover(route)
    st.subheader('Market context')
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
        st.caption('Shaded ±4 bps: illustrative friction band, not an estimated no-arbitrage bound. Actual fees, gas per order, capital costs and redemption frictions depend on trade size and route.')
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
    with st.container(border=True):
        st.subheader('Daily Brief')
        st.write('Read the latest English research brief, with dated observations and source records.')
        st.button('Read Daily Brief →',on_click=route,args=('Daily Brief',))
    with st.container(border=True):
        st.subheader('New to the lab? Follow one question.')
        st.markdown('1. **Observe** a historical price dislocation.\n2. **Inspect** the pool at a recorded block.\n3. **Test** a sale and a liquidity assumption.\n4. **Check** what the model has and has not validated.')


def daily_brief():
    from daily_research_ui import render_daily_research
    render_daily_research()


def historical():
    header('04 / Historical evidence','What happened during the stress?','Read the market evidence first. Historical observations describe an event; model estimates explain a possible execution mechanism.')
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
        fig=go.Figure()
        for token in ['DAI','USDC','USDT']:
            g=shares[shares.asset==token]
            fig.add_trace(go.Bar(x=g.date_utc,y=g.share_pct,name=token,marker_color=TOKEN_COLORS[token]))
        fig.update_layout(barmode='stack',xaxis_title='Snapshot date (UTC)',yaxis_title='Share of token quantities (%)')
        show_chart(fig,300)
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
    if submitted and day is None:
        st.warning('Choose a historical pool date to continue.')
        return
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
    st.table(pd.DataFrame(table))
    st.caption('Price impact compares this trade’s average gross exchange rate with the model’s small-trade marginal rate. It is different from deviation against USD 1. Fees are shown separately; gas is excluded.')
    st.subheader('Sensitivity to pool depth')
    line_chart(pd.DataFrame(saved['sensitivity']),'liquidity_increase_pct',['impact_bps'],'Price impact excluding fee (bps)','Hypothetical increase in pool balances (%)',height=250)
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
    usdc=c1.number_input('USDC held',min_value=0.,max_value=1e10,value=10_000_000.,step=1_000_000.,key='hold_usdc')
    usdt=c2.number_input('USDT held',min_value=0.,max_value=1e10,value=10_000_000.,step=1_000_000.,key='hold_usdt')
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
        with st.status('Running holdings and issuer scenarios…',expanded=True) as status:
            st.write('Initialize historical pool → simulate holder and issuer flows → aggregate holdings')
            st.session_state['hold_result']=(req.model_dump(mode='json'),calculate(portfolio_stress,req))
            status.update(label='Holdings scenario complete',state='complete',expanded=False)
    saved=st.session_state.get('hold_result')
    if not saved:return
    if saved[0]!=req.model_dump(mode='json'):
        st.info('Saved scenario retained with its submitted assumptions. Run again to replace it.')
        req=PortfolioRequest(**saved[0])
        day=str(req.date)
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
        frame=pd.DataFrame(rows).pivot(index='hour',columns='series',values='value').reset_index()
        line_chart(frame,'hour',list(frame.columns[1:]),'Modeled USD quote',height=260)
    with st.expander('Complete assumptions, source metadata & export'):
        st.json(result['request']);st.json(snapshot_detail(result['snapshot']))
        st.write(result['interpretation'])
        json_export(result,'holdings-scenario.json')


def participant_experiment():
    st.caption('Stylized multi-cohort behavioral simulation anchored to exact historical pool states. The SVB reference starts from the pre-crisis March 10 block. Behavioral inputs are explicit scenario assumptions; partial empirical response estimates are reported separately in Data & Contract Evidence.')
    reference=json.loads((ROOT/'svb_reference_fit.json').read_text())
    reference_mode=st.radio('Participant scenario',['SVB path-fitted reference','Custom counterfactual'],key='abm_mode')=='SVB path-fitted reference'
    if reference_mode:
        st.caption('Default parameters minimize squared distance to observed hourly USDC prices. This is an in-sample effective scenario fit; the complete observed and modeled paths are shown below.')
    if reference_mode:
        for key,field in {'abm_date':'date','abm_asset':'stress_asset','abm_pressure':'redemption_pressure_pct','abm_depth':'pool_liquidity_multiplier','abm_panic':'holder_panic','abm_capital':'arbitrage_capital_usd','abm_lp':'lp_max_withdrawal_pct','abm_delay':'issuer_delay_hours','abm_cash':'cash_reserve_ratio_pct'}.items():
            st.session_state[key]=reference['request'][field]
    c1,c2=st.columns(2)
    day=c1.selectbox('Starting pool date',available,index=available.index('2023-03-11'),key='abm_date',disabled=reference_mode)
    asset=c2.selectbox('Stressed token',['USDC','USDT'],key='abm_asset',disabled=reference_mode)
    pressure=c1.slider('Redemption pressure (% of assumed supply)',0.,50.,5.,step=.01,key='abm_pressure',disabled=reference_mode)
    depth=c2.slider('Initial pool depth multiplier',.1,5.,1.,step=.1,key='abm_depth',disabled=reference_mode)
    panic=c1.slider('Holder panic (%)',0.,100.,50.,step=5.,key='abm_panic',help=r'Rule actually implemented: $q_t=\min\{R_t, (Q_0s_r/12)[0.25+1.5h+5(1-P_t)_+]\}$, $h=\mathrm{Panic}/100$. Pool execution is capped and excess demand queues. This is a stylized rule, not an identified panic elasticity.',disabled=reference_mode)
    capital=c2.number_input('Arbitrage capital (USD)',0.,1e11,5e6,step=1e6,key='abm_capital',disabled=reference_mode)
    with st.expander('Issuer and liquidity frictions'):
        delay=st.slider('Issuer processing delay (hours)',0,168,6,key='abm_delay',disabled=reference_mode)
        withdrawal=st.slider('Maximum LP withdrawal (%)',0.,90.,30.,step=5.,key='abm_lp',disabled=reference_mode)
        cash=st.slider('Cash reserve ratio assumption (%)',0.,100.,10.,step=5.,key='abm_cash',disabled=reference_mode)
        treasury=st.checkbox('Enable hypothetical Treasury stress factors',key='abm_treasury',disabled=reference_mode)
        rate=st.slider('Treasury rate shock (bps)',-2000.,2000.,0.,step=100.,key='abm_rate',disabled=reference_mode)
        duration=st.slider('Treasury duration assumption (years)',0.,20.,.25,step=.25,key='abm_duration',disabled=reference_mode)
        frozen=st.slider('Frozen reserves (%)',0.,100.,0.,step=5.,key='abm_frozen',disabled=reference_mode)
    req=AgentExperimentRequest(date=day,stress_asset=asset,redemption_pressure_pct=pressure,pool_liquidity_multiplier=depth,holder_panic=panic,arbitrage_capital_usd=capital,issuer_delay_hours=delay,lp_max_withdrawal_pct=withdrawal,cash_reserve_ratio_pct=cash,treasury_protocol_mode=treasury,rate_shock_bps=rate,asset_duration_years=duration,frozen_reserve_pct=frozen)
    if reference_mode:
        req=AgentExperimentRequest(**reference['request'])
        pass  # Keep the custom submitted run separate from the frozen reference
        st.caption('Reference mode displays the frozen fitted request in read-only controls. Select Custom counterfactual to edit and run a new scenario. Pressure = '+format(req.redemption_pressure_pct,'.4f')+'% of assumed USD 1bn supply; arbitrage capital USD '+format(req.arbitrage_capital_usd,',.0f')+'.')
    else:
        st.warning('Counterfactual stress, not an SVB reconstruction: 15% means USD 150m of global redemption demand under the USD 1bn assumed supply. Extreme pool exhaustion is possible and is not a historical price prediction.')
    canonical_file=ROOT/'canonical_benchmarks.json'
    if canonical_file.exists():
        benchmarks=json.loads(canonical_file.read_text())
        st.session_state.setdefault('abm_result',(benchmarks[0]['request'],benchmarks[0]['result']))
        st.session_state.setdefault('abm_phase',(benchmarks[1]['request'],benchmarks[1]['result']))
    a,b=st.columns(2)
    if a.button('Run participant experiment'):
        with st.status('Simulating participant rules…',expanded=True) as status:
            st.write('Initialize cohorts → apply trading and redemption rules → assess recovery')
            st.session_state['abm_result']=(req.model_dump(mode='json'),calculate(simulate_agents,req))
            status.update(label='Participant experiment complete',state='complete',expanded=False)
    if b.button('Compare 42 pressure / depth combinations'):
        with st.status('Building 42 pressure / depth scenarios…',expanded=True) as status:
            st.write('Evaluate independent parameter combinations and collect sensitivity statistics')
            st.session_state['abm_phase']=(req.model_dump(mode='json'),calculate(phase_diagram,req))
            status.update(label='Sensitivity grid complete',state='complete',expanded=False)
    saved=(reference['request'],reference['result']) if reference_mode else st.session_state.get('abm_result')
    if saved and saved[0]==req.model_dump(mode='json'):
        result=saved[1]
        if reference_mode:
            _a,_b=st.columns(2)
            _a.metric('Observed sampled trough',format(min(r['price'] for r in reference['observed']),'.6f'))
            _b.metric('Fitted path trough',format(min(r['pool_implied_usdc_usd_after_agents'] for r in result['steps']),'.6f'))
        fig=go.Figure(go.Scatter(x=[r['hour'] for r in result['steps']],y=[r['pool_implied_usdc_usd_after_agents'] for r in result['steps']],name='Modeled quote'))
        if reference_mode:
            fig.add_trace(go.Scatter(x=[r['hour'] for r in reference['observed']],y=[r['price'] for r in reference['observed']],name='Observed hourly USDC'))
            st.caption('In-sample path RMSE: '+format(reference['rmse_bps'],'.2f')+' bps. '+reference['limitations'])
        fig.update_layout(xaxis_title='Hours after exact historical pool block',yaxis_title='USD per USDC')
        show_chart(fig,380)
        with st.expander('Participant flows and model state'):
            path_chart(result['steps'],['dai_pool','usdc_pool','usdt_pool'],'Pool token quantities')
            st.json(result['summary']);st.json(req.model_dump(mode='json'))
        json_export(result,'participant-experiment.json')
    elif saved:
        st.info('Saved run retained; inputs changed. Run again to replace it.')
        path_chart(saved[1]['steps'],['pool_implied_usdc_usd_after_agents'],'Saved modeled quote')
    phase=st.session_state.get('abm_phase')
    if phase:
        if phase[0]!=req.model_dump(mode='json'):st.caption('Sensitivity grid retains its own submitted assumptions; download includes the exact request.')
        frame=pd.DataFrame(phase[1]['cells'])
        grid=frame.pivot(index='liquidity_multiplier',columns='redemption_pressure_pct',values='max_move_from_initial_pct')
        fig=go.Figure(go.Heatmap(x=list(grid.columns),y=list(grid.index),z=grid.values,colorscale='Blues',colorbar=dict(title='Move (pp)')))
        fig.update_layout(xaxis_title='Redemption pressure (%)',yaxis_title='Pool depth multiplier')
        show_chart(fig,300)
        json_export(phase[1],'participant-sensitivity.json')


def stress_test():
    header('05 / Microstructure simulation','Multi-cohort liquidity experiments.','Historical pool anchors, explicit behavioral rules and reproducible sensitivity experiments.')
    strip('Observed starting state + hypothetical dynamics · Canonical SVB reference preloaded · No live quotes or trades')
    cohorts,sale,holdings=st.tabs(['Multi-Cohort Dynamics & Sensitivity Grid','Single-Order Market Impact','Institutional Balance-Sheet Scenarios'])
    with cohorts:participant_experiment()
    with sale:sale_experiment()
    with holdings:holdings_experiment()


def mechanism_lab():
    from mechanism_ui import render_mechanism_lab
    render_mechanism_lab()


def forecast_lab():
    from forecast_lab_ui import render_forecast_lab
    render_forecast_lab(market_rows)

def empirical_evidence():
    from empirical_ui import render_evidence
    render_evidence()

def journal():
    from experiment_journal import render_journal
    render_journal()

def validation():
    header('09 / Evidence standards','Know what the model can support.','Compare forecast baselines, inspect model assumptions and trace the underlying data. See which results have been checked and which remain research hypotheses.')
    forecast_tab,execution_tab,data_tab,roadmap_tab=st.tabs(['Forecast validation','Execution & scenario models','Data & provenance','Research roadmap'])
    with forecast_tab:
        from forecast_ui import render_forecast_research
        render_forecast_research(market_rows)
    with execution_tab:
        st.subheader('Validation status')
        st.write('Forecast Lab reports threshold autoregression, chronological interval calibration and observed-covariate ablations. Co-TSFA and JEPA remain explicitly labeled experimental architectures; no trained result is implied. Exact-block solver evidence and effective-response estimation are published in Data & Contract Evidence.')
        table=[
            {'Component':'Curve execution model','Evidence available':'Historical balances, A, fee and block metadata; numerical consistency checks','What remains open':'Broader pools, additional blocks, token-rate edge cases and transaction-level reconciliation','Status':'Exact-block benchmark published'},
            {'Component':'Rule-based participant model','Evidence available':'Explicit cohort rules, reproducible parameters and sensitivity experiments','What remains open':'Calibration to observed trading/redemption flows and held-out event testing','Status':'Uncalibrated'},
            {'Component':'Holdings scenarios','Evidence available':'Independent token paths and separate original-pool sale estimates','What remains open':'Joint price dynamics, correlations and synchronized valuation','Status':'Synthetic scenario'},
            {'Component':'Daily English brief','Evidence available':'Saved structured facts and generation timestamp','What remains open':'Source freshness, interval calibration and factual review','Status':'Deterministic econometric template'},
        ]
        st.table(pd.DataFrame(table))
        st.subheader('What numerical checks establish')
        st.write('Tests check conservation through the gross-output invariant, fee arithmetic, scale consistency, and execution-cost sensitivity across trade sizes. Passing these checks does not establish agreement with the historical Curve contract or realized trades.')
        st.subheader('How the execution estimate works')
        st.write('The solver computes the three-token StableSwap invariant using recorded balances and amplification A, then solves for the output balance after the input sale. A proportional fee is deducted from gross output. Liquidity counterfactuals scale all balances while preserving composition, A and fees.')
        st.subheader('How the holdings scenario works')
        st.write('Finite holder selling, constrained arbitrage, issuer queues and optional liquidity withdrawals evolve in hourly steps. Inputs such as frozen reserves, cash ratios and issuer delays are assumptions. Independent USDC and USDT runs are combined into a synthetic holdings path; no joint market model is estimated.')
        st.caption('No calibrated probability of safety, personal redemption ETA, statistical VaR or execution guarantee is produced.')
    with data_tab:
        st.subheader('Three different clocks')
        st.table(pd.DataFrame([
            {'Dataset':'Recent USD prices','Clock':market_date+' UTC','Source':'CoinGecko market_chart','Meaning':'Last sampled observation in each completed UTC day'},
            {'Dataset':'Historical USD prices','Clock':str(prices.date_utc.min())+' → '+str(prices.date_utc.max()),'Source':'DefiLlama / underlying CoinGecko identifiers','Meaning':'Hourly samples aggregated by UTC day; not exchange OHLC'},
            {'Dataset':'Historical pool snapshots','Clock':available[0]+' → '+available[-1],'Source':'Ethereum JSON-RPC · Curve 3pool','Meaning':'Sparse exact-block state; missing dates are not interpolated'}
        ]))
        st.write('USD prices and pool balances are not synchronized. Token balance totals must not be presented as dollar-valued reserves. Pool swap rates describe relative exchange rates; USD depeg measurement uses an independent USD series.')
        report=saved_report()
        if report:
            with st.expander('Daily brief generation record'):
                st.write('Generated (UTC): '+report['facts']['generated_at_utc'])
                st.write('Generation engine: deterministic, source-linked econometric reporting.')
                st.write('Scheduled for 09:15 Asia/Shanghai through GitHub Actions. Schedules can be delayed; failed market-data updates retain the previous dated report.')
        for name in ['data/manifest.json','data/processed/curve_3pool_manifest.json']:
            file=ROOT/name
            if file.exists():
                with st.expander('Inspect '+name):
                    st.json(json.loads(file.read_text()))
        st.link_button('Curve 3pool contract','https://etherscan.io/address/0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7#code')
    with roadmap_tab:
        st.subheader('Next evidence to earn')
        st.write('**1 · Execution accuracy.** Five historical blocks, three order sizes and both USDC/USDT directions are benchmarked against archived contract get_dy responses. Actual errors and raw units are available in Data & Contract Evidence.')
        st.write('**2 · Event calibration.** Fit participant parameters to observed flows, then evaluate on complete held-out stress events. Report sensitivity and failure cases.')
        st.write('**3 · Forecast robustness.** Add event-level holdouts, interval coverage, stress-regime errors and multiple seeds before claiming predictive value.')
        st.write('**4 · Representation learning.** JEPA remains a proposed experiment. Compare persistence, a supervised backbone and the same backbone with pretraining on chronological splits. The architecture is a proposed controlled experiment, with no trained JEPA result currently reported.')
        st.caption('This roadmap describes future research, not current capabilities.')

try:
    {'Overview':overview,'Daily Brief':daily_brief,'Forecast Lab':forecast_lab,'Historical Research':historical,'Liquidity Stress Test':stress_test,'Mechanism Lab':mechanism_lab,'Data & Contract Evidence':empirical_evidence,'Experiment Journal':journal,'Models & Validation':validation}[page]()
except (ValueError,LookupError,KeyError,OSError) as exc:
    st.error('This analysis could not be completed. Check the selected data and inputs.')
    with st.expander('Analysis details'):st.write(str(exc))
st.divider()
st.caption('Stablecoin Stress Lab · Observed evidence, explicit assumptions, reproducible experiments. Research estimates do not establish future performance.')

_retained=dict(st.session_state.get('_retained_inputs',{}))
for _key in list(st.session_state):
    if _key.startswith(('abm_','model_','sale_','hold_','connected_','v3_','regime_','empirical_','research_','curve_')) and _key!='model_csv' and not _key.endswith(('result','phase')):
        _retained[_key]=st.session_state[_key]
st.session_state['_retained_inputs']=_retained
