"""Model leaderboard, common evaluation windows and honest research status."""
import json
from datetime import datetime,timezone,date
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from model_lab import evaluate,saved_chronos,fingerprint,VERSION
from terminal_charts import show
from experiment_journal import record

@st.cache_data(show_spinner=False,max_entries=30)
def cached_evaluation(rows,asset,horizon,artifact):
    return evaluate(rows,asset,horizon,artifact)


def render_forecast_lab(default_rows):
    st.markdown('<div class="eyebrow">02 / Model comparison</div>',unsafe_allow_html=True)
    st.title('Forecast Lab')
    st.write('Test whether a model improves on carrying the last observed price forward. Compare peg deviations on identical chronological windows.')
    source=st.selectbox('Research dataset',['Saved daily observations','Upload daily CSV'],key='model_dataset')
    rows=default_rows
    if source=='Upload daily CSV':
        file=st.file_uploader('Daily USD prices',type=['csv'],key='model_csv',help='date_utc, asset, close_usd; USDC and USDT; ≥45 consecutive daily observations each. Only the last 90 per asset are used.')
        if file is None:return
        if file.size>2_000_000:raise ValueError('Use a CSV smaller than 2 MB.')
        frame=pd.read_csv(file)
        if not {'date_utc','asset','close_usd'}<=set(frame.columns):raise ValueError('Required columns: date_utc, asset, close_usd.')
        rows=frame.to_dict('records')
    asset_col,horizon_col=st.columns(2)
    asset=asset_col.selectbox('Asset',['USDC','USDT'],key='model_asset')
    horizon=horizon_col.select_slider('Forecast horizon (days)',options=[1,3,7],value=1,key='model_horizon')
    artifact=saved_chronos(rows)
    with st.status('Compare models on shared rolling origins',expanded=False) as status:
        result=cached_evaluation(rows,asset,horizon,artifact)
        status.update(label='Model comparison ready',state='complete')
    run_id=record('Forecast comparison',dict(asset=asset,horizon_days=horizon,dataset_sha256=result['dataset_sha256'],version=VERSION),result)
    age=(datetime.now(timezone.utc).date()-date.fromisoformat(result['as_of'])).days
    st.markdown(f'<div class="data-strip">AS OF {result["as_of"]} UTC · {result["observations"]} observations · {horizon}-day horizon · RUN {run_id}</div>',unsafe_allow_html=True)
    if age>2:st.warning(f'Historical observations: {age} days old. These projections do not describe today’s market.')
    scores=pd.DataFrame(result['scores'])
    scores=scores.rename(columns=dict(model='Model',n='Origins',mae_bps='MAE (bps)',rmse_bps='RMSE (bps)',worst_error_bps='Worst error (bps)',improvement_pct='Improvement vs persistence (%)',stress_n='Stress targets',stress_mae_bps='Stress MAE (bps)'))
    st.subheader('Common-window leaderboard')
    st.dataframe(scores,hide_index=True,width='stretch',column_config={c:st.column_config.NumberColumn(format='%.3f') for c in ['MAE (bps)','RMSE (bps)','Worst error (bps)','Improvement vs persistence (%)','Stress MAE (bps)']})
    st.caption('Errors are measured in basis points of USD 1. Positive improvement means lower MAE than persistence. Every model uses the same ≤20 origins; each forecast sees only earlier observations in this evaluation loop. Multi-day target windows overlap, so errors are not independent.')
    if not result['scores'][0]['stress_n']:
        st.info('No selected targets deviated by ≥100 bps from USD 1. This sample cannot establish performance during depegs; stress metrics remain empty.')
    a,b=st.tabs(['Projection comparison','Held-out errors'])
    with a:
        fig=go.Figure();frame=pd.DataFrame(result['projections'])
        for model,g in frame.groupby('model',sort=False):
            fig.add_trace(go.Scatter(x=g.date_utc,y=g.deviation_bps,name=model,mode='lines+markers'))
        fig.add_hline(y=0,line_dash='dash',line_color='#8193aa')
        fig.update_layout(xaxis_title='Projected date (UTC)',yaxis_title='Deviation from USD 1 (bps)')
        fig.update_xaxes(type='category')
        show(fig,key='model_projection')
        st.caption('Point projections, not event probabilities. Rolling mean uses the last seven observed values as a fixed forecast; AR(1) and boosting recurse forward. The same fixed settings are used at every origin; no hyperparameters are selected on this evaluation set.')
    with b:
        frame=pd.DataFrame(result['predictions']);fig=go.Figure()
        for model,g in frame.groupby('model',sort=False):
            fig.add_trace(go.Scatter(x=g.target,y=(g.prediction_usd-g.actual_usd)*10000,name=model,mode='lines+markers'))
        fig.add_hline(y=0,line_dash='dash',line_color='#8193aa');fig.update_layout(xaxis_title='Held-out target date (UTC)',yaxis_title='Signed forecast error (bps)')
        show(fig,key='model_errors')
        st.dataframe(frame,hide_index=True,width='stretch')
    with st.expander('Model registry & evidence'):
        st.dataframe(pd.DataFrame([
            dict(Model='Persistence',Method='Last observation carried forward',Status='Executed baseline'),
            dict(Model='Rolling mean (7d)',Method='Seven-observation mean',Status='Executed baseline'),
            dict(Model='AR(1)',Method='Peg deviation autoregression, bounded coefficient',Status='Executed statistical model'),
            dict(Model='Gradient boosting',Method='Lag 1/2/3/7, mean/std 7d and last change; 50 shallow trees',Status='Executed nonlinear model'),
            dict(Model='Chronos-2',Method='Frozen pretrained Amazon model; saved CPU inference',Status='Executed artifact matching this dataset' if artifact else 'No matching inference artifact'),
            dict(Model='Co-TSFA',Method='Anomaly-oriented contrastive training regularizer',Status='Research proposal; not trained or scored')]),hide_index=True,width='stretch')
        if artifact:st.json(artifact['metadata'])
        else:st.caption('Chronos-2 is omitted from the leaderboard when the dataset fingerprint differs from the saved inference artifact. No substitute prediction or fabricated score is shown.')
        st.write('Pretrained-model data overlap has not been independently audited. Chronological input slicing does not prove that pretraining never saw historical test observations. No financial alpha, causal inference or depeg probability is established.')
        st.json(result['training_config'])
    with st.expander('Co-TSFA research plan'):
        st.write('Research status: not implemented as a trained model. Compare the same encoder with and without anomaly-oriented contrastive regularization. Tune only on training events; hold out complete stress events, evaluate normal and stress periods separately, and report results across seeds. Synthetic corruptions are not substitutes for real depeg events.')
        st.markdown('[TMLR publication listing](https://jmlr.org/tmlr/papers/) · [Author implementation](https://github.com/caisr-hh/Co-TSFA-Contrastive-Time-Series-Forecasting-with-Anomalies) · [Chronos-2 code and report](https://github.com/amazon-science/chronos-forecasting)')
    st.download_button('Download comparison and experiment record',json.dumps(result,indent=2),'forecast-comparison-'+run_id+'.json','application/json')
    st.caption('The experiment is also available in Experiment Journal for this session. Forecast accuracy is distinct from a profitable trading strategy; transaction costs and executable orders are not modeled here.')
