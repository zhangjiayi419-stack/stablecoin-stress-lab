"""Frozen forward-event forecasts and observable cross-event data provenance."""
import json,hashlib
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from terminal_charts import show
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'cross_event_study'
MODELS=['Persistence / zero price change','GB price-only','GB + observed covariates']
LABELS={'Terra_2022_05':'Terra · May 2022','FTX_2022_11':'FTX · November 2022','SVB_2023_03':'SVB · March 2023'}

@st.cache_data(show_spinner=False)
def _load(name,modified):return json.loads((OUT/name).read_text())
def load(name):return _load(name,(OUT/name).stat().st_mtime_ns)

def render_cross_event():
    result=load('results.json');protocol=load('protocol.json')
    st.markdown('<div class="eyebrow">03 / Retrospective out-of-event test</div>',unsafe_allow_html=True)
    st.title('Can a model transfer to the next crisis?')
    st.write('Fixed one-hour-ahead forecasts trained on earlier events only. Compare observed microstructure features against price-only GB and carrying the latest observed price forward.')
    st.warning('Retrospective event transfer, not preregistered prospective evidence. These events and model families were previously viewed. No model is tuned or refitted inside the test event; all losing results are retained. One Curve pool only.')
    a,b=st.columns(2)
    asset=a.selectbox('Transfer asset',['USDC','USDT'],key='transfer_asset')
    event=b.selectbox('Forward test event',['FTX_2022_11','SVB_2023_03'],format_func=lambda e:LABELS[e],key='transfer_event')
    fold=next(f for f in result['folds'] if f['asset']==asset and f['test_event']==event)
    st.markdown('**Training events:** '+', '.join(LABELS[e] for e in fold['train_events'])+' → **test:** '+LABELS[event]+'. Terra is the earliest training event; it is never scored using future events.')
    st.table(pd.DataFrame([
      {'Partition':'Model fit','Examples':fold['fit_examples'],'UTC start':fold['fit_start'],'UTC end':fold['fit_end']},
      {'Partition':'Frozen interval calibration','Examples':fold['calibration_examples'],'UTC start':fold['calibration_start'],'UTC end':fold['calibration_end']},
      {'Partition':'Test origins / resolved targets','Examples':fold['test_examples'],'UTC start':fold['test_start'],'UTC end':fold['test_end']}]))
    st.caption('Seven observed hourly price lags; 24 contiguous preceding hours for volume normalization. A next-hour price already known at the origin is excluded. Models share identical test origins within each asset/fold; different assets can have different eligible targets. No interpolation.')
    frame=pd.DataFrame(fold['scores'])
    names={'MAE_bps':'MAE (bps)','RMSE_bps':'RMSE (bps)','Max_error_bps':'Maximum error (bps)','MAE_skill_vs_persistence_pct':'MAE skill vs persistence (%)','Stress_targets':'Stress targets','Stress_MAE_bps':'Stress MAE (bps)','Coverage_pct':'Coverage (%)','Mean_width_bps':'Interval width (bps)','Winkler_bps':'Winkler score (bps)'}
    def table(cols):
        view=frame[cols].rename(columns=names)
        numeric={names.get(c,c):'{:,.3f}' for c in cols if c not in ['Model','Targets','Stress_targets']}
        st.table(view.style.format(numeric,na_rep='Not observed'))
    st.subheader('Point forecasts · identical held-out targets')
    table(['Model','Targets','MAE_bps','RMSE_bps','Max_error_bps','MAE_skill_vs_persistence_pct'])
    st.caption('Skill = 100 × (1 − model MAE / persistence MAE). Negative values mean worse. Persistence is also the zero-price-change null; it is not counted twice. Bps are relative to USD 1.')
    st.subheader('Pressure subset · observed peg deviation >100 bps')
    table(['Model','Stress_targets','Stress_MAE_bps'])
    st.caption('Two-sided absolute USD deviation >100 bps at the target observation; not issuer default. Small stress counts limit interpretation.')
    st.subheader('Frozen nominal 90% intervals · no test feedback')
    table(['Model','Coverage_pct','Mean_width_bps','Winkler_bps'])
    st.caption('Last 32 eligible training examples calibrate the residual radius after fitting on earlier examples. Finite-sample 90% quantile is frozen before the test event. Temporal dependence and event shift invalidate a per-event coverage guarantee. Low coverage is reported directly; intervals are not widened after seeing test outcomes.')
    best=next(r for r in fold['scores'] if r['Model']=='GB + observed covariates')
    plain=next(r for r in fold['scores'] if r['Model']=='GB price-only')
    gain=100*(1-best['MAE_bps']/plain['MAE_bps'])
    st.info(f"Covariate ablation in this fold: {gain:+.2f}% MAE improvement versus price-only GB; {best['MAE_skill_vs_persistence_pct']:+.2f}% skill versus persistence. These comparisons answer different questions; neither is a trading-profit estimate.")
    selected=st.selectbox('Inspect transfer model',MODELS,key='transfer_model')
    rs=pd.DataFrame([r for r in fold['predictions'] if r['model']==selected])
    rs['target_clock']=pd.to_datetime(rs.target,utc=True)
    rs=rs.set_index('target_clock').reindex(pd.date_range(rs.target_clock.min(),rs.target_clock.max(),freq='h'))
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=rs.index,y=rs.lower_bps,line=dict(width=0),showlegend=False,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=rs.index,y=rs.upper_bps,line=dict(width=0),fill='tonexty',fillcolor='rgba(112,183,255,.15)',name='Frozen nominal 90% interval'))
    fig.add_trace(go.Scatter(x=rs.index,y=rs.actual_bps,name='Observed',line=dict(color='#dfb969')))
    fig.add_trace(go.Scatter(x=rs.index,y=rs.prediction_bps,name=selected))
    fig.update_layout(xaxis_title='Held-out target cutoff (UTC)',yaxis_title='USD peg deviation (bps)');show(fig,380,key='transfer_forecast')
    st.caption('Line gaps mark excluded targets, not interpolated prices. USD observations are provider samples, not exchange OHLC or executable quotes; sampling noise can dominate small deviations.')
    st.subheader('Interpretation and limits')
    st.write('The same covariate set does not transfer consistently. A finite tree ensemble trained on smaller historical dislocations can fail to extrapolate a new event. This is a hypothesis consistent with the observed error pattern, not a causal explanation established by two event folds.')
    for limitation in result['limitations']:st.caption('• '+limitation)
    from experiment_journal import record
    run_id=record('Retrospective forward event transfer',dict(asset=asset,test_event=event,protocol_sha256=result['protocol_sha256'],feature_sha256=result['feature_sha256'],seed=419),fold)
    st.caption('Executed artifact · '+result['version']+' · run '+run_id+' · generated '+result['generated_at_utc'].replace('T',' ').replace('+00:00',' UTC'))
    with st.expander('Fixed protocol, exclusions and exports'):
        st.json(protocol);st.json(load('example_exclusions_'+asset+'.json'))
        st.write('Protocol SHA-256: '+result['protocol_sha256']);st.write('Feature SHA-256: '+result['feature_sha256'])
        st.download_button('Download transfer experiment',json.dumps(result,indent=2),'forward-event-transfer.json','application/json')
        st.download_button('Download all fold metrics (CSV)',(OUT/'scores.csv').read_bytes(),'forward-event-scores.csv','text/csv')
        st.download_button('Download all predictions (CSV)',(OUT/'predictions.csv').read_bytes(),'forward-event-predictions.csv','text/csv')
    render_cross_event_data('export_cross_forecast')


def render_cross_event_data(key_prefix='cross_event_data'):
    meta=load('collection_manifest.json');coverage=load('coverage.json');manifest=load('manifest.json')
    st.subheader('Observed cross-event covariate data')
    a,b,c=st.columns(3);a.metric('Aligned hourly feature rows',f"{manifest['feature_rows']:,}");b.metric('Pool event logs across windows',f"{meta['pool_events']:,}");c.metric('Cutoff-block gas headers',f"{meta['gas_header_count']:,}")
    st.caption(f"New collection: {meta['new_price_observations']:,} price observations and {meta['completed_log_intervals']} complete Terra/FTX hourly log intervals; SVB source data is reused and fingerprinted. Counts overlap prior archives and must not be added as independent evidence.")
    st.table(pd.DataFrame(coverage).rename(columns={'event':'Event','state_cutoffs':'State cutoffs','aligned_intervals':'Aligned hours','raw_events':'Log events','first_cutoff':'First feature cutoff UTC','last_cutoff':'Last cutoff UTC','missing_price_intervals':'Excluded price intervals'}))
    st.markdown('**Observable inputs:** cutoff-known USD-marked imbalance; trailing-volume spike; exact-state USDC→USDT slippage slope (fixed direction for both asset experiments); multicoin LP additions/removals; single-coin removal count; invariant-decline proxy; cutoff-block base fee. LP single-coin amounts are not assigned a token or invented USD value. Base fee is not gas actually paid by a transaction.')
    st.caption('Event intervals are (previous state block, current state block]. USD prices are last samples at/before cutoff and at most 2h old. Each log query covers ≤100 blocks with deduplication/cap checks. Six selected swap logs reconcile with transaction receipts. An invariant decline is confounded by fees and amplification, not identified LP withdrawal behavior.')
    with st.expander('Coverage exclusions, source hashes and raw downloads'):
        st.json(load('alignment_exclusions.json'));st.json(meta);st.json(load('receipt_checks.json'))
        for name,label,mime in [('microstructure_features.csv','Download aligned cross-event features (CSV)','text/csv'),('prices_hourly.json','Download source price observations','application/json'),('pool_events.json.gz','Download collected/reused pool logs','application/gzip'),('gas_headers.json','Download cutoff gas headers','application/json'),('protocol.json','Download frozen study protocol','application/json'),('manifest.json','Download cross-event data manifest','application/json')]:
            st.download_button(label,(OUT/name).read_bytes(),name,mime,key=key_prefix+'_'+name)
        for name in meta['raw_shards']:
            st.download_button('Download raw response shard '+name,(OUT/name).read_bytes(),name,'application/gzip',key=key_prefix+'_'+name)
