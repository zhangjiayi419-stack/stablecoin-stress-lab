import json
import os
from datetime import date
from pathlib import Path
import pandas as pd
import altair as alt
import streamlit as st
from forecast_brief import context, forecast, fetch_current, generate_brief

@st.cache_data(ttl=3600, show_spinner=False)
def current_prices():
    return fetch_current()


def render_forecast(history_rows, brief_page=False):
    st.title('English Daily Brief' if brief_page else 'Stablecoin Forecast')
    st.caption('Daily USD price research · statistical baseline · source dates shown explicitly')
    latest = Path(__file__).resolve().parent/'reports/latest.json'
    if brief_page and not latest.exists():
        st.info('No scheduled brief has been saved yet.')
    if brief_page and latest.exists():
        with st.expander('Latest scheduled report', expanded=True):
            saved = json.loads(latest.read_text())
            st.caption('Generated at '+saved['facts']['generated_at_utc'])
            observed = date.fromisoformat(saved['facts']['assets'][0]['as_of'])
            from datetime import datetime, timezone
            if (datetime.now(timezone.utc).date() - observed).days > 2:
                st.warning('This saved report is stale. Check the data date and scheduled job.')
            st.markdown(saved['markdown'])
    snapshot = Path(__file__).resolve().parent/'reports/prices_latest.json'
    options = ['Bundled historical data','Recent CoinGecko USD data','Upload daily CSV']
    if snapshot.exists():
        options.insert(0, 'Latest daily snapshot')
    source = st.selectbox('Forecast data', options)
    if source == 'Recent CoinGecko USD data':
        st.caption('CoinGecko API; latest completed UTC days; cached for one hour.')
        if st.button('Refresh market data'):
            current_prices.clear()
        with st.spinner('Fetching USD observations…'):
            rows = current_prices()
    elif source == 'Latest daily snapshot':
        rows = json.loads(snapshot.read_text())
    elif source == 'Upload daily CSV':
        uploaded = st.file_uploader('CSV: date_utc, asset (USDC/USDT), close_usd, optional source',type='csv')
        if uploaded is None:
            st.info('Upload at least 45 consecutive daily observations per asset.')
            return
        if uploaded.size > 2_000_000:
            raise ValueError('CSV must be smaller than 2 MB.')
        rows = pd.read_csv(uploaded).to_dict('records')
    else:
        rows = history_rows
    facts = context(rows)
    st.caption('Generation time (UTC): '+facts['generated_at_utc'])
    if facts['status'] == 'historical':
        st.warning(f"Historical data: latest observation is {facts['data_age_days']} days old. This is not today's market outlook.")
    st.info('AR(1) baseline with a 90% residual-bootstrap model interval. Intervals may understate stress risk; no calibrated depeg probability is provided.')
    horizon = st.select_slider('Forecast horizon (days)',options=[1,3,7],value=7)
    facts['assets'] = [forecast(rows, asset, horizon) for asset in ('USDC','USDT')]
    for asset in ('USDC','USDT'):
        result = forecast(rows,asset,horizon)
        st.subheader(asset+' · as of '+result['as_of']+' UTC')
        c1,c2,c3 = st.columns(3)
        c1.metric('Latest observed USD',f"${result['latest_usd']:.6f}")
        c2.metric('Deviation from $1',f"{result['deviation_bps']:.2f} bps")
        c3.metric(f'{horizon}-day baseline',f"${result['forecast'][-1]['forecast_usd']:.6f}")
        frame = pd.DataFrame(result['forecast'])
        base = alt.Chart(frame).encode(x=alt.X('date_utc:T',title='Forecast date (UTC)'))
        band = base.mark_area(opacity=.18).encode(y=alt.Y('lower_90:Q',title='USD',scale=alt.Scale(zero=False)),y2='upper_90:Q')
        curve = base.mark_line(point=True).encode(y='forecast_usd:Q',tooltip=['date_utc','forecast_usd','lower_90','upper_90'])
        st.altair_chart(band+curve,use_container_width=True)
        st.dataframe(frame,hide_index=True)
        v=result['validation']
        st.caption(f"Expanding-window one-day validation, {v['n']} held-out observations: AR(1) MAE ${v['mae_usd']:.6f}; persistence MAE ${v['persistence_mae_usd']:.6f}. Multi-day intervals are not independently validated.")
    st.download_button('Download forecast facts',json.dumps(facts,indent=2),'forecast-facts.json','application/json')
    if brief_page:
        st.subheader('Generate an English research brief')
        # Public visitors never trigger a paid request using the server owner's key.
        enabled = os.getenv('ALLOW_MANUAL_LLM','false').lower() == 'true'
        if not enabled:
            st.info('Manual generation is disabled. Run the daily job or enable ALLOW_MANUAL_LLM=true for a private local session.')
        elif st.button('Write English brief with Alibaba Qwen',type='primary'):
            with st.spinner('Writing an English brief from the displayed data…'):
                st.session_state['english_brief']=(facts['assets'],generate_brief(facts))
        saved=st.session_state.get('english_brief')
        if saved and saved[0] == facts['assets']:
            st.markdown(saved[1])
            st.download_button('Download English brief',saved[1],'stablecoin-daily-brief.md','text/markdown')
    with st.expander('Model and sources'):
        st.write(facts['assets'][0]['model'])
        st.write('Last 90 observations, minimum 45 consecutive days. Fit uses earlier observations only. Bootstrap: 1,000 paths, fixed seed 419; fitted-parameter uncertainty is omitted.')
        st.write(facts['scope'])
        st.write(facts['sources'])
