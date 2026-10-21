"""Exact-block exploration and execution using the Oct21 public archive extension."""
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from snapshot_archive import ARCHIVE,EVENTS,load_archive,event_rows,execution
from terminal_charts import show

@st.cache_data(show_spinner=False)
def cached_archive(modified_ns):return load_archive()

def archive_data():return cached_archive((ARCHIVE/'unique_pool_states.json').stat().st_mtime_ns)

def render_archive(compact=False):
    rows,m=archive_data()
    st.subheader('Multi-event exact-block archive')
    a,b,c=st.columns(3)
    a.metric('Audited block snapshots',f'{len(rows):,}')
    b.metric('New blocks vs prior data',f"{m['new_blocks_vs_prior_73_and_346']:,}")
    c.metric('Historical event windows',str(len(m['per_event'])))
    st.caption('Oct 21 archive extension: 843 successfully collected cutoffs = 843 unique Ethereum blocks; 181 overlap prior collections. The original 73-state replay catalog and 346-state empirical dataset remain separately versioned. Do not add these counts as independent observations.')
    st.info('These blocks are now available for browsing and exact-state sell-order calculations. Frozen forecasts and SVB participant-fit results retain their original datasets and anchors; new snapshots do not imply retraining or external behavioral validation.')
    if compact:
        coverage_table(m)
        downloads(m,'evidence_archive')
        return
    event=st.selectbox('Archive event',list(EVENTS),key='archive_event')
    selected=event_rows(rows,EVENTS[event]);dates=sorted({r['requested_cutoff_utc'][:10] for r in selected})
    center={'SVB · March 2023':'2023-03-11','Terra · May 2022':'2022-05-12','FTX · November 2022':'2022-11-09'}[event]
    # Widget choices have stable event-specific keys; changing events cannot carry an invalid date/block.
    day=st.selectbox('Archive cutoff date (UTC)',dates,index=dates.index(center),key='archive_date_'+EVENTS[event])
    candidates=event_rows(rows,EVENTS[event],day)
    block=st.selectbox('Exact historical block',candidates,format_func=lambda r:f"{r['requested_cutoff_utc'][11:19]} cutoff · block {r['block_number']:,} · {r['timestamp']} actual",key='archive_block_'+EVENTS[event]+'_'+day)
    st.caption(f"Selected block {block['block_number']:,} · {block['block_hash']} · cutoff lag {block['cutoff_lag_seconds']}s. All balances, A, fee and archived get_dy were read at this same block.")
    frame=pd.DataFrame(selected)
    chart=go.Figure()
    total=frame[['dai_pool','usdc_pool','usdt_pool']].sum(axis=1)
    for name,color in [('DAI','#dfb969'),('USDC','#70b7ff'),('USDT','#48d5b4')]:
        chart.add_trace(go.Scatter(x=frame.timestamp,y=100*frame[name.lower()+'_pool']/total,name=name,mode='lines',line=dict(color=color)))
    chart.add_vline(x=block['timestamp'],line_dash='dot',line_color='#b8c8da')
    chart.update_layout(xaxis_title='Actual historical block time (UTC)',yaxis_title='Share of normalized token quantities (%)')
    show(chart,350,key='archive_composition')
    st.caption('Token-quantity shares are not USD value weights. Uneven sampling is intentional; connecting lines are a visual guide, not reconstructed intermediate states. The vertical line identifies the selected block.')
    st.table(pd.DataFrame([{'Token':t,'Pool tokens':block[t.lower()+'_pool']} for t in ['DAI','USDC','USDT']]).style.format({'Pool tokens':'{:,.4f}'}))
    a,b=st.columns(2);a.metric('Historical Curve A',f"{block['amp']:,}");b.metric('Historical swap fee (bps)',f"{block['fee_rate']*10000:.4f}")
    st.subheader('Single-order execution at this exact block')
    amount=st.number_input('USDC sold (tokens)',min_value=1.,max_value=1e10,value=1e6,step=10000.,key='archive_sell_amount')
    q=execution(block,amount)
    a,b,c=st.columns(3);a.metric('Estimated net USDT output',f"{q['net_output']:,.4f}");b.metric('Average net USDT per USDC',f"{q['average_execution_price_net']:.6f}");c.metric('Ex-fee impact (%)',f"{q['price_impact_ex_fee_pct']:.4f}")
    st.caption('Deterministic quote conditional on recorded pool state; USDT per USDC is not an independent USD price. This does not execute a trade or simulate participant feedback. No gas or MEV adjustment is applied.')
    st.write(f"**Archived contract check at this block:** 1,000,000 USDC → {block['contract_quote_1m_usdc_to_usdt']:,.6f} USDT; Python relative error **{block['solver_relative_error_bps']:.10f} bps**. This check applies to this direction and amount only.")
    with st.expander('Block provenance, coverage and export'):
        st.json(block);coverage_table(m)
        result=dict(experiment='Exact-block archive single order',block=block,request=dict(input_token='USDC',output_token='USDT',input_tokens=amount),result=q,dataset_sha256=m['files']['unique_pool_states.json'])
        st.download_button('Download selected block and quote',json.dumps(result,indent=2),'exact-block-quote.json','application/json')
        st.download_button('Download event block states (CSV)',frame.to_csv(index=False),'archive-'+EVENTS[event]+'.csv','text/csv')
        downloads(m,'historical_archive')
    with st.expander('Solver validation across all 843 blocks'):
        st.write(f"Maximum |relative error| across the collected 1m USDC→USDT checks: **{m['maximum_solver_relative_error_bps']:.10f} bps**. Six fixed blocks independently matched a second public RPC for both block hash and contract quote.")
        st.json(json.loads((ARCHIVE/'validation_report.json').read_text()))
        st.download_button('Download independent provider checks',(ARCHIVE/'independent_provider_crosschecks.json').read_bytes(),'independent-provider-crosschecks.json','application/json')


def coverage_table(m):
    st.table(pd.DataFrame([dict(Event=e,Cutoffs=v['cutoff_observations'],Unique_blocks=v['unique_blocks'],New_blocks=v['new_blocks'],UTC_start=v['start'],UTC_end=v['end']) for e,v in m['per_event'].items()]))
    st.caption('6-hour sampling over ±14 days, hourly over ±3 days; SVB March11–13 adds 15-minute sampling. One Curve pool, three named event windows. More timestamps do not establish independent causal events or structural calibration.')

def downloads(m,prefix):
    for name,label,mime in [('unique_pool_states.json','Download all 843 block states','application/json'),('new_unique_pool_states.csv','Download 662 newly added blocks (CSV)','text/csv'),('manifest.json','Download archive manifest','application/json'),('raw_responses.jsonl.gz','Download raw RPC responses (gzip JSONL)','application/gzip')]:
        st.download_button(label,(ARCHIVE/name).read_bytes(),name,mime,key=prefix+'_'+name)
