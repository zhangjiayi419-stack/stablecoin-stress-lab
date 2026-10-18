"""Structured deterministic reporting with explicitly dated calibrated intervals."""
import json
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
import streamlit as st
from empirical_ui import artifact
ROOT=Path(__file__).resolve().parent


def clean_time(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def render_daily_research():
    st.markdown('<div class="eyebrow">Daily / Econometric bulletin</div>',unsafe_allow_html=True)
    st.title('Daily Research Brief')
    data=artifact('econometric_results.json');rows=[]
    for asset in ['USDC','USDT']:
        c=data['contexts']['recent|'+asset];r=data['results']['recent|'+asset+'|7|Bounded ACI'];f=r['forecast']['SETAR'];score=next(s for s in r['scores'] if s['Model']=='SETAR')
        rows.append({'Asset':asset,'Observation date (UTC)':c['as_of'],'Spot USD':c['latest_usd'],'Deviation (bps)':(c['latest_usd']-1)*10000,
            '7D SETAR forecast':f['prediction_usd'],'Nominal 90% interval':f"[{f['lower_usd']:.6f}, {f['upper_usd']:.6f}]",
            'OOS MAE (bps)':score['MAE_bps'],'Empirical coverage (%)':score['Coverage_pct'],'Winkler score (bps)':score['Winkler_bps']})
    dates=sorted({r['Observation date (UTC)'] for r in rows})
    st.caption('Observations: '+', '.join(dates)+' UTC · Research artifact generated: '+clean_time(data['generated_at_utc']))
    age=(datetime.now(timezone.utc).date()-datetime.fromisoformat(dates[-1]).date()).days
    if age>2:st.warning(f'This is a dated research snapshot ({age} days old), not today’s market bulletin.')
    st.write('**Generation engine:** deterministic, source-linked econometric template. Numerical tables are generated from executed research artifacts; no language model is used to invent commentary.')
    st.subheader('Market snapshot & calibrated outlook')
    frame=pd.DataFrame(rows)
    st.table(frame.style.format({'Spot USD':'{:.6f}','Deviation (bps)':'{:+.3f}','7D SETAR forecast':'{:.6f}','OOS MAE (bps)':'{:.3f}','Empirical coverage (%)':'{:.2f}','Winkler score (bps)':'{:.3f}'}))
    st.caption('Intervals are bounded adaptive-conformal residual intervals. Coverage and Winkler score are measured on completed seven-day targets; overlapping windows are dependent. The nominal 90% level is not a calibrated depeg probability or a guarantee for the next observation.')
    st.subheader('Research interpretation')
    st.write('Stablecoin prices can remain close to par while execution depth deteriorates. Compare point-error, empirical coverage and interval width together. Low MAE in a calm window does not establish crisis robustness; inspect the historical SVB evaluation and observed onchain covariate ablation in Forecast Lab.')
    st.write('The deterministic template retains all model comparisons in Forecast Lab, including models that underperform persistence. SETAR uses a training-only threshold; no ranking or investment outcome is guaranteed.')
    st.markdown('**Primary feed:** CoinGecko Market Data API v3 via the saved market snapshot · 90D rolling UTC last sample. **Historical stress feed:** DefiLlama historical USD samples. These are sampled observations, not exchange OHLC.')
    report=json.loads((ROOT/'reports/latest.json').read_text())
    with st.expander('Source URLs, data clocks & reproducible facts'):
        for source in report['facts'].get('sources',[]):st.write(source)
        st.caption('The saved daily-report job and the heavier econometric artifact have independent refresh clocks. This table always displays its own observation dates and generation time; a newer price report does not silently refresh SETAR or conformal results.')
        st.json(data['contexts']);st.json({a:data['results']['recent|'+a+'|7|Bounded ACI']['dataset_sha256'] for a in ['USDC','USDT']})
    text='# Stablecoin Econometric Research Brief\n\n'+'| '+' | '.join(frame.columns)+' |\n| '+' | '.join(['---']*len(frame.columns))+' |\n'+'\n'.join('| '+' | '.join(str(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None))+'\n\nGenerated: '+clean_time(data['generated_at_utc'])+'\n\nNominal intervals; empirical coverage only. Not a trading recommendation.'
    # No optional markdown dependency is needed for downloadable structured facts.
    st.download_button('Download research brief data',json.dumps(dict(generated_at_utc=data['generated_at_utc'],rows=rows),indent=2),'daily-econometric-brief.json','application/json')
    st.download_button('Download English research brief',text,'daily-econometric-brief.md','text/markdown')
