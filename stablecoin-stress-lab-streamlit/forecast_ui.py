"""Research-only forecast workspace with explicit comparison against persistence."""
import json
import plotly.graph_objects as go
from terminal_charts import show
import pandas as pd
import streamlit as st
from forecast_brief import context, forecast, fetch_current

@st.cache_data(ttl=3600,show_spinner=False)
def current_prices():
    return fetch_current()


def render_forecast_research(default_rows):
    st.subheader('Can the model beat a simple baseline?')
    st.write('This is an experimental daily-price model. Compare its held-out errors with carrying the last observed price forward before interpreting its outlook.')
    source=st.selectbox('Evaluation dataset',['Latest saved daily observations','Refresh from CoinGecko','Upload daily CSV'],key='validation_source')
    rows=default_rows
    if source=='Refresh from CoinGecko':
        if st.button('Refresh observations',key='validation_refresh'):
            current_prices.clear()
        with st.spinner('Fetching completed UTC days…'):
            rows=current_prices()
    elif source=='Upload daily CSV':
        file=st.file_uploader('Daily USD observations',type=['csv'],help='Columns: date_utc, asset, close_usd. At least 45 consecutive days for USDC and USDT.')
        if file is None:
            st.caption('Upload a CSV to begin. No interpolation is performed.')
            return
        if file.size>2_000_000:
            raise ValueError('Please use a CSV smaller than 2 MB.')
        rows=pd.read_csv(file).to_dict('records')
    facts=context(rows)
    if facts['status']=='historical':
        st.warning(f"Historical dataset · observations are {facts['data_age_days']} days old. This is not a current outlook.")
    table=[]
    for result in facts['assets']:
        v=result['validation'];relative=100*(1-v['mae_usd']/v['persistence_mae_usd']) if v['persistence_mae_usd'] else None
        table.append({'Asset':result['asset'],'As of (UTC)':result['as_of'],'Held-out days':v['n'],
                      'AR(1) MAE (USD)':v['mae_usd'],'Persistence MAE (USD)':v['persistence_mae_usd'],
                      'Error reduction vs persistence (%)':relative,
                      'Result':'Lower error' if relative is not None and relative>0 else 'No improvement'})
    st.dataframe(pd.DataFrame(table),hide_index=True,width='stretch',column_config={
        'AR(1) MAE (USD)':st.column_config.NumberColumn(format='%.7f'),
        'Persistence MAE (USD)':st.column_config.NumberColumn(format='%.7f'),
        'Error reduction vs persistence (%)':st.column_config.NumberColumn(format='%.2f')})
    st.caption('One-day MAE = mean absolute USD price error. Expanding-window evaluation starts after 30 observations; each fit uses only earlier data. Error reduction below zero means the model did worse. These are descriptive results for this sample, not statistical significance tests.')
    st.divider()
    asset=st.selectbox('Inspect asset',['USDC','USDT'],key='forecast_asset')
    horizon=st.select_slider('Projection horizon (days)',[1,3,7],value=7,key='projection_horizon')
    result=forecast(rows,asset,horizon)
    st.caption(f"Model origin: {result['as_of']} UTC · fitted on {result['observations']} daily observations")
    frame=pd.DataFrame(result['forecast'])
    frame['utc_date']=frame.date_utc.astype(str)
    frame['persistence_usd']=result['latest_usd']
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=frame.date_utc,y=frame.lower_90,line=dict(width=0),showlegend=False,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=frame.date_utc,y=frame.upper_90,line=dict(width=0),fill='tonexty',fillcolor='rgba(112,183,255,.18)',name='Conditional 90% interval'))
    fig.add_trace(go.Scatter(x=frame.date_utc,y=frame.forecast_usd,mode='lines+markers',name='AR(1)',line=dict(color='#70b7ff')))
    fig.add_trace(go.Scatter(x=frame.date_utc,y=frame.persistence_usd,name='Persistence',line=dict(color='#8fa2b9',dash='dash')))
    fig.update_layout(xaxis_title='Projection date (UTC)',yaxis_title='USD')
    fig.update_yaxes(tickformat='.6f')
    show(fig,300)
    st.caption('Blue: AR(1) · shaded: conditional 90% residual-bootstrap model interval · dashed: persistence. Multi-day intervals have not been independently validated. They are not calibrated depeg probabilities.')
    with st.expander('Specification, projection table & reproducible export'):
        st.write(result['model'])
        st.write('Minimum 45 consecutive daily observations; maximum 90. Coefficient constrained to [-0.98, 0.98]. Residual bootstrap: 1,000 paths, fixed seed 419. Parameter uncertainty, liquidity shocks and issuer fundamentals are excluded.')
        st.dataframe(frame,hide_index=True,width='stretch')
        payload=dict(facts,inspected_projection=result)
        st.download_button('Download evaluation and projection',json.dumps(payload,indent=2),'forecast-validation.json','application/json')
