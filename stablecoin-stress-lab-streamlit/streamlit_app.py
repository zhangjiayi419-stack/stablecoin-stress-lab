"""Community Cloud entrypoint, reusing the project's Python numerical models."""
from datetime import date
from pathlib import Path
import csv
import io
import json
import time
from threading import BoundedSemaphore
import pandas as pd
import altair as alt
import streamlit as st
from backend.app.domain.schemas import AgentExperimentRequest, PortfolioRequest, QuoteRequest
from backend.app.services.portfolio import portfolio_stress, risk_workflow
from backend.app.services.agents import simulate_agents, phase_diagram
from backend.app.services.experiment import calculate_experiment
from backend.app.services.replay import load_history, load_pool_state

st.set_page_config(page_title='Stablecoin Stress Lab',page_icon='◈',layout='wide')
st.markdown('''<style>.stMainBlockContainer{padding-top:2rem} h1{letter-spacing:-.03em} .stMarkdown p{line-height:1.8} [data-testid="stMetricValue"]{font-size:2rem}</style>''',unsafe_allow_html=True)

@st.cache_data
def history_data(): return load_history(),load_pool_state()
@st.cache_resource
def calculation_slots(): return BoundedSemaphore(2)
def calculate(fn,request):
    timestamps=st.session_state.setdefault('calculations',[])
    now=time.monotonic();timestamps[:]=[t for t in timestamps if t>now-60]
    if len(timestamps)>=12: raise ValueError('Demo limit: 12 calculations per minute. Please wait.')
    slots=calculation_slots()
    if not slots.acquire(False): raise ValueError('Demo is busy; please retry shortly.')
    try: timestamps.append(now);return fn(request)
    finally: slots.release()

def export_csv(result):
    buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['path','value'])
    def flatten(value,path='result'):
        if isinstance(value,dict):
            for k,v in value.items():flatten(v,path+'.'+str(k))
        elif isinstance(value,list):
            for i,v in enumerate(value):flatten(v,path+'.'+str(i))
        else:writer.writerow([path,value])
    flatten(result);return '\ufeff'+buf.getvalue()

def line(rows,fields,title):
    frame=pd.DataFrame(rows)
    frame=frame.melt(id_vars=['hour'],value_vars=fields,var_name='series',value_name='value')
    chart=alt.Chart(frame).mark_line().encode(x=alt.X('hour:Q',title='Hour'),y=alt.Y('value:Q',title=title,scale=alt.Scale(zero=False)),color='series:N',tooltip=['hour:Q','series:N','value:Q'])
    st.altair_chart(chart,use_container_width=True)

history,snapshots=history_data()
prices=pd.DataFrame(history['prices']);prices['close_usd']=pd.to_numeric(prices['close_usd'])
available=sorted({s['timestamp'][:10] for s in snapshots})
pages=['My stablecoin check','Risk Assistant','Historical replay','Pool & slippage','ABM sandbox','Interactive Agents','Events & sources','Methodology','Forecasting Research']
with st.sidebar:
    st.title('Stablecoin Stress Lab')
    page=st.radio('Workspace',pages)
    if page=='Historical replay':
        selected=st.date_input('Selected UTC price date',value=date(2023,3,11),min_value=date.fromisoformat(prices.date_utc.min()),max_value=date.fromisoformat(prices.date_utc.max())).isoformat()
    else:
        selected=st.selectbox('Sourced snapshot date',available,index=available.index('2023-03-11'))
        st.caption('Only dates with real pool snapshots are selectable.')
    st.caption('Research demo · hypothetical, uncalibrated scenarios · no trades executed.')

presets={'Bank reserve freeze':dict(scenario='bank_freeze',panic_pct=70,cash_ratio_pct=10,issuer_delay_hours=24,frozen_reserve_pct=20,rate_shock_bps=0,lp_withdrawal_pct=10,treasury_duration_years=.25,treasury_yield_pct=4),
'Redemption rush + LP exits':dict(scenario='run_lp',panic_pct=95,cash_ratio_pct=5,issuer_delay_hours=12,frozen_reserve_pct=0,rate_shock_bps=0,lp_withdrawal_pct=60,treasury_duration_years=.25,treasury_yield_pct=4),
'Rate rise + duration loss':dict(scenario='rate_hike',panic_pct=50,cash_ratio_pct=10,issuer_delay_hours=6,frozen_reserve_pct=0,rate_shock_bps=300,lp_withdrawal_pct=20,treasury_duration_years=2.,treasury_yield_pct=4)}

def portfolio_inputs():
    c1,c2=st.columns(2)
    usdc=c1.number_input('USDC tokens',0.,1e10,1e6,step=1000.,key='hold_usdc')
    usdt=c2.number_input('USDT tokens',0.,1e10,5e5,step=1000.,key='hold_usdt')
    preset=st.selectbox('One-click hypothetical scenario',list(presets),key='scenario')
    values=presets[preset].copy()
    with st.expander('Advanced assumptions · optional'):
        for key,value in list(values.items()):
            if key=='scenario':continue
            limit=2000 if key=='rate_shock_bps' else 168 if key=='issuer_delay_hours' else 20 if key=='treasury_duration_years' else 100
            minimum=-2000 if key=='rate_shock_bps' else 0
            values[key]=st.number_input(key.replace('_',' ').title(),float(minimum),float(limit),float(value),key='preset_'+preset+key,help='Hypothetical model input, not an observed issuer rule.')
        values['issuer_delay_hours']=int(values['issuer_delay_hours'])
    return PortfolioRequest(date=selected,usdc_amount=usdc,usdt_amount=usdt,**values)

try:
 if page in ['My stablecoin check','Risk Assistant']:
    st.title('How could a shock affect my holdings?' if page=='My stablecoin check' else 'Risk Assistant')
    st.caption('Holdings remain in session memory; this application does not save them. Hosting infrastructure may retain technical logs.')
    req=portfolio_inputs()
    if st.button('Check my holdings' if page=='My stablecoin check' else 'Analyze current holdings',type='primary'):
        with st.spinner('Checking sources and calculating scenarios…'):
            output=calculate(portfolio_stress if page=='My stablecoin check' else risk_workflow,req)
        st.session_state['retail_output']=(page,req.model_dump(mode='json'),output)
    saved=st.session_state.get('retail_output')
    if saved and saved[:2]==(page,req.model_dump(mode='json')):
        output=saved[2];r=output if page=='My stablecoin check' else output['result']
        st.warning('Hypothetical scenario · not a forecast, actual loss or VaR.')
        columns=st.columns(3)
        for col,label,key in zip(columns,['Reference holdings value','Maximum modeled mark loss','Modeled peak-to-trough drop'],['reference_portfolio_usd','maximum_mark_loss_vs_reference_usd','maximum_path_drawdown_usd']): col.metric(label,f"${r[key]:,.2f}")
        if page=='Risk Assistant':
            st.header('What this means & next steps')
            for paragraph in output['report']:st.markdown('#### '+paragraph)
            with st.expander('Analysis trace'):
                for stage in output['stages']:st.write(stage['role']+' — '+stage['message'])
        line(r['portfolio_path'],['modeled_portfolio_usd'],'Synthetic portfolio value (USD)')
        st.subheader('Separate historical pool sale estimates')
        st.dataframe(pd.DataFrame(r['independent_sale_estimates']),hide_index=True,use_container_width=True)
        st.caption('Independent trades on the original snapshot; not simultaneous liquidation. Do not add sale differences to mark loss.')
        st.subheader('Conventional USDC vs hypothetical Treasury token')
        rows=[]
        for name,result in r['comparison'].items():
            for step in result['steps']:rows.append({'hour':step['hour'],'series':name,'value':step['pool_implied_usdc_usd_after_agents']})
        st.altair_chart(alt.Chart(pd.DataFrame(rows)).mark_line().encode(x='hour:Q',y=alt.Y('value:Q',title='Modeled USD quote',scale=alt.Scale(zero=False)),color='series:N',tooltip=['hour','series','value']),use_container_width=True)
        with st.expander('Assumptions, sources and limitations'):
            st.write('Scenario assumptions')
            for key,value in r['request'].items():st.write(f"**{key.replace('_',' ').title()}:** {value}")
            st.write('**Snapshot:** '+r['snapshot']['timestamp']);st.write('**Source:** '+r['snapshot']['source']);st.write(r['interpretation'])
        st.download_button('Download reproducible CSV',export_csv(output),file_name='stablecoin-stress-report.csv',mime='text/csv')
 elif page=='Historical replay':
    st.title('Historical USD price replay')
    st.caption('Daily last sampled hourly observation; source times differ from pool blocks. News overlap is not causation.')
    rows=prices[prices.date_utc==selected]
    for asset,col in zip(['USDC','USDT'],st.columns(2)):
        row=rows[rows.asset==asset].iloc[0];col.metric(asset,f"${row.close_usd:.6f}",f"{(row.close_usd-1)*10000:.1f} bps from $1")
    frame=prices.copy();frame['time']=pd.to_datetime(frame.date_utc)
    st.altair_chart(alt.Chart(frame).mark_line().encode(x=alt.X('time:T',title='Time (UTC)'),y=alt.Y('close_usd:Q',title='USD',scale=alt.Scale(zero=False)),color='asset:N',tooltip=['date_utc','asset',alt.Tooltip('close_usd:Q',format='.6f')]),use_container_width=True)
 elif page=='Pool & slippage':
    st.title('Historical Curve 3pool execution estimate')
    amount=st.number_input('Sell USDC',1.,1e10,1e6);increase=st.slider('Hypothetical liquidity increase (%)',0,100,30)
    if st.button('Calculate quote'):
        r=calculate(calculate_experiment,QuoteRequest(date=selected,sell_amount_usdc=amount,liquidity_increase_pct=increase))
        for col,key,label in zip(st.columns(2),['historical_model_estimate','counterfactual_model_estimate'],['Historical snapshot model estimate','Hypothetical liquidity assumption']):
            col.subheader(label);col.metric('USDT out, net',f"{r[key]['net_usdt_out']:,.2f}");col.metric('Price impact, fee excluded',f"{r[key]['price_impact_ex_fee_pct']:.5f}%")
        st.caption(r['interpretation']);st.write(r['snapshot']['source'])
    st.dataframe(pd.DataFrame(snapshots)[['timestamp','dai_pool','usdc_pool','usdt_pool']],hide_index=True)
 elif page in ['ABM sandbox','Interactive Agents']:
    st.title(page)
    st.warning('Market participants are rule-based ABM cohorts, not AI language-model agents.')
    values={'date':selected}
    groups={
      'Market Microstructure':['retail_share_pct','whale_share_pct','arbitrageur_share_pct','arbitrage_capital_usd','holder_panic','arbitrage_response_pct'],
      'Protocol Frictions':['cash_reserve_ratio_pct','issuer_delay_hours','issuer_capacity_usdc_per_hour','gas_cost_usd','reserve_settlement_hours','weekend_bank_friction'],
      'Macro Shocks':['duration_hours','circulating_supply_usdc','redemption_pressure_pct','pool_liquidity_multiplier'],
      'Treasury Stress Factors':['treasury_protocol_mode','frozen_reserve_pct','freeze_release_hours','credit_rating','collateral_exposure_pct','collateral_impairment_pct','credit_event_mode','credit_base_annual_pd_pct','random_seed','shock_hour','base_risk_free_rate_pct','rate_shock_bps','rate_ramp_hours','asset_duration_years','treasury_asset_share_pct','defi_yield_pct','stablecoin_yield_pct','yield_chaser_share_pct','yield_response_pct','yield_switch_cost_bps','yield_holding_days','lp_max_withdrawal_pct','lp_risk_threshold_bps','lp_response_pct']}
    for group,fields in groups.items():
      with st.expander(group,expanded=group=='Market Microstructure'):
        for key in fields:
            field=AgentExperimentRequest.model_fields[key];default=field.default;label=key.replace('_',' ').title()
            if isinstance(default,bool):values[key]=st.checkbox(label,default,key='agent_'+key)
            elif isinstance(default,str):values[key]=st.selectbox(label,['AAA','AA','A','BBB','BB','B'] if key=='credit_rating' else ['forced','sampled'],key='agent_'+key)
            else:
                limits={}
                for meta in field.metadata:
                    for attr in ['ge','gt','le']:
                        if hasattr(meta,attr):limits[attr]=getattr(meta,attr)
                low=limits.get('ge',limits.get('gt',0)+1e-6)
                high=limits.get('le',1e12)
                val=st.number_input(label,float(low),float(high),float(default),key='agent_'+key)
                values[key]=int(val) if field.annotation is int else val
    req=AgentExperimentRequest(**values)
    if page=='ABM sandbox':
      if st.button('Build 42-cell phase diagram',type='primary'):
        with st.spinner('Computing phase diagram…'):st.session_state['phase_cloud']=(values.copy(),calculate(phase_diagram,req))
      saved=st.session_state.get('phase_cloud')
      if saved and saved[0]==values:
        frame=pd.DataFrame(saved[1]['cells']);selection=alt.selection_point(name='cell',fields=['redemption_pressure_pct','liquidity_multiplier'])
        chart=alt.Chart(frame).mark_rect().encode(x=alt.X('redemption_pressure_pct:O',title='Redemption pressure (%)'),y=alt.Y('liquidity_multiplier:O',title='Pool depth multiplier',sort='descending'),color=alt.Color('max_move_from_initial_pct:Q',title='Move from start (pp)'),tooltip=list(frame.columns)).add_params(selection)
        event=st.altair_chart(chart,use_container_width=True,on_select='rerun',selection_mode=['cell'])
        selected_cells=event.selection.get('cell',[])
        if selected_cells:
            cell=selected_cells[0];req=req.model_copy(update={'redemption_pressure_pct':float(cell['redemption_pressure_pct']),'pool_liquidity_multiplier':float(cell['liquidity_multiplier'])})
            result=calculate(simulate_agents,req);line(result['steps'],['pool_implied_usdc_usd_after_agents'],'Modeled USDC USD quote');st.write('Maximum discount:',result['summary']['max_depeg_depth_pct'],'%; recovery hour:',result['summary']['recovery_hour'])
    else:
      if st.button('Run participant scenario',type='primary'):
        result=calculate(simulate_agents,req);line(result['steps'],['pool_implied_usdc_usd_after_agents'],'Modeled USD quote');line(result['steps'],['dai_pool','usdc_pool','usdt_pool'],'Pool token balances');line(result['steps'],['lp_cumulative_withdrawal_pct'],'LP withdrawal (%)');st.download_button('Download scenario CSV',export_csv(result),'agent-scenario.csv','text/csv')
 elif page=='Events & sources':
    st.title('Historical events & sources')
    st.caption('Curated news windows; temporal overlap does not establish causation. No automatic parameter changes are made from news.')
    for event in history['events']:
        with st.expander(event['summary']):
            st.write(event['start_utc']+' — '+event['end_utc']);st.write(event.get('price_series_note',''))
            for source in history['sources']:
                if source['event_id']==event['event_id']:st.link_button('Original source',source['source_url'])
 elif page=='Methodology':
    st.title('Methodology & limitations')
    st.markdown('''### Curve execution
The 3-token invariant uses contract A, floating-point iteration, recorded pool balances and fees. Quotes approximate historical execution and do not reproduce integer rounding exactly.

### Market ABM
Finite retail selling, FIFO institutional redemptions, capital-constrained arbitrage and optional yield exits / LP withdrawal run in hourly steps. Treasury rates, duration, freezes and credit quality are user assumptions, not actual issuer measurements. Recovery requires six consecutive hourly observations within 1% of $1 after the trough.

### Holdings check
Independent token simulations form a synthetic portfolio path; correlations and joint market dynamics are not estimated. Mark losses, original-pool sale estimates and cohort queues have different meanings and must not be added. No personal redemption ETA or statistical VaR is produced.

### Risk workflow
Inspired by FinAgent orchestration. Deterministic Python stages inspect data, run models, audit interpretation and create template reports. No LLM, MCP/A2A network or autonomous trading is connected.

### Data
Historical USD prices were sampled and aggregated by UTC day; daily min/max are not exchange OHLC. Sparse Ethereum snapshots record block identifiers and actual timestamps. Historical prices and pool state can differ in time. Event sources are curated independently.

### Limits
Uncalibrated research prototype. No investment prediction, proof of safety or product-superiority claim. Source metadata and complete assumptions are included in exports.''')
    st.link_button('FinAgent paper','https://arxiv.org/abs/2512.02227')
 elif page=='Forecasting Research':
    st.title('JEPA forecasting research');st.warning('NOT TRAINED · NO FORECAST AVAILABLE')
    st.write('Proposed experiment: collect continuous hourly inputs, compare persistence / supervised backbone / the same backbone with JEPA pretraining, split chronologically, hold out complete stress events, and evaluate errors and event false alarms across multiple seeds. JEPA gains depend on backbone; the paper does not establish stablecoin forecasting performance.')
    st.link_button('JEPA paper','https://arxiv.org/abs/2609.31680')
except (ValueError,LookupError,KeyError) as exc:
    st.error(str(exc))
st.caption('Stablecoin Stress Lab · Research prototype · Hypothetical simulations are not historical observations.')
