"""Evidence-led forecast regimes and chain verification surfaces."""
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from terminal_charts import show,lines
from experiment_journal import record
ROOT=Path(__file__).resolve().parent

@st.cache_data(show_spinner=False)
def _artifact(name,modified_ns):return json.loads((ROOT/'empirical_data'/name).read_text())

def artifact(name):
    return _artifact(name,(ROOT/'empirical_data'/name).stat().st_mtime_ns)


def score_table(rows):
    names={'MAE_bps':'MAE (bps)','Coverage_pct':'Coverage (%)','Mean_width_bps':'Mean interval width (bps)','Winkler_bps':'Winkler score (bps)','Stress_targets':'Stress targets (>100 bps)','Stress_MAE_bps':'Stress MAE (bps)','Improvement_pct':'MAE improvement vs persistence (%)'}
    frame=pd.DataFrame(rows).rename(columns=names)
    st.table(frame.style.format({c:'{:,.3f}' for c in frame.columns if c not in ('Model','Targets','Stress targets (>100 bps)')},na_rep='Not observed'))


def render_regime_study():
    st.markdown('<div class="eyebrow">02 / Econometric evaluation</div>',unsafe_allow_html=True)
    st.title('Forecast Lab')
    st.write('Chronological regime evaluation, threshold dynamics and calibrated prediction intervals. Results include unsuccessful models.')
    a,b=st.columns([2,1])
    regime=a.selectbox('Evaluation regime',['Recent 90D window','Historical stress window · SVB 2023'],key='research_regime')
    asset=b.selectbox('Stressed asset',['USDC','USDT'],key='research_asset')
    a,b=st.columns(2)
    h=a.select_slider('Endpoint forecast horizon (days)',[1,3,7],value=1,key='research_horizon')
    mode=b.selectbox('Interval calibration',['Bounded ACI','Rolling conformal'],key='research_calibration')
    key=f'{"svb" if regime.startswith("Historical") else "recent"}|{asset}|{h}|{mode}'
    result=artifact('econometric_results.json')['results'][key]
    run_id=record('Chronological interval evaluation',dict(regime=regime,asset=asset,horizon=h,calibration=mode,dataset_sha256=result['dataset_sha256']),result)
    st.caption(f'Frozen, executed research snapshot · {result["version"]} · run {run_id} · nominal interval coverage 90%')
    st.subheader('Shared-window out-of-sample evidence')
    score_table(result['scores'])
    rows=pd.DataFrame(result['predictions']);start=rows.target.min();end=rows.target.max()
    st.caption(f'Evaluation targets: {start} → {end} UTC. Identical origins across models. Metrics are endpoint errors in bps of USD 1; multi-day windows overlap. Stress means realized absolute USD-peg deviation strictly greater than 100 bps.')
    if not any(s['Stress_targets'] for s in result['scores']):
        st.info('No >100 bps target in this sample. Switch to the SVB window for observed USDC stress. Zero USDT stress targets are retained when USDT did not cross the threshold; they are not filled with synthetic cases.')
    selected=st.selectbox('Inspect model',['SETAR','Persistence','AR(1)','Rolling mean (7d)','Gradient boosting'],key='interval_model')
    rs=rows[rows.model==selected];fig=go.Figure()
    fig.add_trace(go.Scatter(x=rs.target,y=(rs.lower_usd-1)*10000,line=dict(width=0),showlegend=False,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=rs.target,y=(rs.upper_usd-1)*10000,line=dict(width=0),fill='tonexty',fillcolor='rgba(112,183,255,.16)',name='Nominal 90% interval'))
    fig.add_trace(go.Scatter(x=rs.target,y=(rs.prediction_usd-1)*10000,name=selected,mode='lines'))
    fig.add_trace(go.Scatter(x=rs.target,y=(rs.actual_usd-1)*10000,name='Observed',line=dict(color='#dfb969')))
    fig.update_layout(xaxis_title='Held-out target date (UTC)',yaxis_title='Peg deviation (bps)');show(fig,key='regime_intervals')
    st.caption('Intervals are formed before the target is observed. Warm-up residuals are excluded from the leaderboard. ACI updates only after a target resolves; its bounded finite-quantile implementation does not guarantee coverage for each crisis or each horizon.')
    with st.expander('Latest projection and complete protocol'):
        latest=result['forecast'][selected];st.json(latest);st.write(result['protocol'])
        st.latex(r'z_t=10^4(P_t-1),\quad z_{t+1}=\begin{cases}a_1+\phi_1z_t,&|z_t|\le c\\a_2+\phi_2z_t,&|z_t|>c\end{cases}')
        st.write('SETAR thresholds are chosen only inside each training prefix from its 50th/65th/80th absolute-deviation quantiles, with at least five transitions per regime. The threshold is re-estimated at each origin; coefficients are bounded to ±0.98.')
        st.latex(r'\alpha_{t+1}=\mathrm{clip}\{\alpha_t+0.02(0.10-\mathbf{1}[Y_t\notin C_t])\},\qquad S_\alpha(L,U;y)=U-L+\frac{2}{\alpha}(L-y)_++\frac{2}{\alpha}(y-U)_+')
        st.write('Coverage must be interpreted with width and Winkler score. A wide interval can cover a crisis while being uninformative. Chronos-2 is kept in its separate frozen-foundation comparison; no conformal score is fabricated for a model without the same residual history.')
        st.json(result['model_settings']);st.download_button('Download interval evaluation',json.dumps(result,indent=2),'interval-evaluation-'+run_id+'.json','application/json')
    st.divider();st.subheader('Observed onchain covariate ablation · one-hour horizon')
    cov=artifact('covariate_results.json');score_table(cov['results'][asset]['scores'])
    st.write(cov['specification'])
    st.caption('This separate experiment uses March 7–17 hourly Curve data, not the daily leaderboard above. Pool imbalance, volume spike and slippage slope are measured from collected state/logs. No hourly-to-daily score comparison or guaranteed baseline improvement is claimed.')
    with st.expander('Covariate data, alignment and source fingerprint'):
        st.write('Feature fingerprint: '+cov['feature_sha256']);st.write(artifact('manifest.json')['clocks'])
        st.download_button('Download hourly covariate experiment',json.dumps(cov,indent=2),'hourly-covariate-ablation.json','application/json')


def render_evidence():
    st.markdown('<div class="eyebrow">07 / Chain evidence</div>',unsafe_allow_html=True)
    st.title('Data & Contract Evidence')
    m=artifact('manifest.json');cols=st.columns(4)
    for col,label,number in zip(cols,['State snapshots','Raw pool events','Hourly feature rows','Contract quote checks'],[m['state_count'],m['raw_event_count'],m['hourly_feature_count'],m['contract_quotes']]):col.metric(label,f'{number:,}')
    coverage,solver,estimation=st.tabs(['Coverage & clocks','Exact-block get_dy','Effective response estimation'])
    with coverage:
        st.table(pd.DataFrame([
            dict(Dataset='USD sampled prices',Window='2023-01-01 → 2023-04-15',Frequency='Hourly provider observations; daily close = last sample per UTC date',Source=m['price_source']),
            dict(Dataset='Curve 3pool state',Window='Jan–Apr daily plus Mar 7–17 hourly',Frequency='Exact historical blocks at or before requested cutoff',Source=m['rpc']),
            dict(Dataset='Curve pool events',Window='2023-03-07 → 2023-03-17',Frequency='All address logs in consecutive block intervals; transaction/log-index deduplication',Source=m.get('log_source','Ethereum indexed logs'))]))
        st.write(m['clocks']);st.write('Collected (UTC): '+m['retrieved_at_utc'])
        for text in m['limitations']:st.caption('• '+text)
        st.json(m['files'])
        st.write('Documented alignment exclusions:');st.json(m.get('alignment_exclusions',[]))
        raw_manifest=artifact('raw_archive_manifest.json')
        st.caption(f"Raw archive: {raw_manifest['raw_response_count']:,} original public API responses with requests and retrieval timestamps.")
        st.download_button('Download raw response archive (gzip JSONL)',(ROOT/'empirical_data/raw_responses.jsonl.gz').read_bytes(),'raw_responses.jsonl.gz','application/gzip')
        st.json(raw_manifest['files'])
        st.download_button('Download data manifest',json.dumps(m,indent=2),'empirical-manifest.json','application/json')
        st.download_button('Download aligned microstructure features',pd.DataFrame(artifact('microstructure_features.json')).to_csv(index=False),'curve-aligned-hourly-features.csv','text/csv')
    with solver:
        frame=pd.DataFrame(artifact('contract_benchmarks.json'))
        st.write('Five historical blocks × three input sizes × two USDC/USDT directions. These are actual historical eth_call responses, not model-generated reference values. Five collected logs were independently checked against RPC transaction receipts.')
        st.metric('Maximum absolute relative error',f"{abs(frame.relative_error_bps).max():.8f} bps")
        visible=frame[['block_number','block_time','direction','input_tokens','contract_output_tokens','python_output_tokens','relative_error_bps']].rename(columns={'block_number':'Ethereum block','block_time':'Block time (UTC)','direction':'Direction','input_tokens':'Input tokens','contract_output_tokens':'Contract get_dy','python_output_tokens':'Python float64','relative_error_bps':'Relative error (bps)'})
        st.dataframe(visible.style.format({'Input tokens':'{:,.0f}','Contract get_dy':'{:,.6f}','Python float64':'{:,.6f}','Relative error (bps)':'{:.8f}'}),hide_index=True,width='stretch')
        st.caption('Error = (Python output − contract output) / contract output × 10,000. Raw token units, decimals and block hashes are preserved in the export. This finite benchmark supports these tested configurations; it is not a proof for every Curve pool or trade.')
        st.download_button('Download raw quote benchmark',frame.to_csv(index=False),'curve-contract-validation.csv','text/csv')
    with estimation:
        fit=artifact('response_estimation.json');st.write(fit['method'])
        st.latex(r'w_{t+1}=c+\beta\,(100(1-P_t))_++\rho w_t+\epsilon_{t+1}')
        rows=[dict(Parameter=k,Estimate=v,Lower_90=fit['bootstrap_90'][k][0],Upper_90=fit['bootstrap_90'][k][1]) for k,v in fit['coefficients'].items()]
        st.table(pd.DataFrame(rows).style.format({k:'{:,.5f}' for k in ['Estimate','Lower_90','Upper_90']}))
        st.write(f"Chronological training: {fit['train_n']} transitions through {fit['train_end']}. Held out: {fit['test_n']} from {fit['test_start']}.")
        a,b=st.columns(2);a.metric('Holdout MAE (percentage points)',f"{fit['holdout_mae_pct']:.5f}");b.metric('Zero-response MAE (pp)',f"{fit['zero_response_mae_pct']:.5f}")
        st.caption('90% ranges: 100 moving-block bootstrap fits, six-hour blocks, seed 419. They describe resampling uncertainty within one event, not population-wide structural confidence.')
        st.warning(fit['limitations'])
        st.download_button('Download estimation record',json.dumps(fit,indent=2),'effective-response-estimation.json','application/json')
