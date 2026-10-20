"""Five-block landing page: purpose, evidence, experiment, next step, author."""
import json
from pathlib import Path
import streamlit as st
ROOT=Path(__file__).resolve().parent
REPO='https://github.com/zhangjiayi419-stack/stablecoin-stress-lab'


def findings():
    empirical=json.loads((ROOT/'empirical_data/econometric_results.json').read_text())
    scores=empirical['results']['svb|USDC|1|Bounded ACI']['scores']
    gb=next(r for r in scores if r['Model']=='Gradient boosting')
    hourly=json.loads((ROOT/'empirical_data/covariate_results.json').read_text())
    cov=next(r for r in hourly['results']['USDC']['scores'] if r['Model']=='GB + observed covariates')
    price_only=next(r for r in hourly['results']['USDC']['scores'] if r['Model']=='GB price-only')
    observations=json.loads((ROOT/'empirical_data/prices_hourly.json').read_text())
    low=min(r['price_usd'] for r in observations if r['asset']=='USDC' and '2023-03-09'<=r['timestamp']<'2023-03-16')
    manifest=json.loads((ROOT/'empirical_data/manifest.json').read_text())
    return dict(low=low,improvement=gb['Improvement_pct'],targets=gb['Targets'],covariate_improvement=cov['Improvement_pct'],solver_error=manifest['maximum_solver_error_bps'],quotes=manifest['contract_quotes'],stress_targets=gb['Stress_targets'],stress_mae=gb['Stress_MAE_bps'],price_only_improvement=price_only['Improvement_pct'],ablation_gain=100*(1-cov['MAE_bps']/price_only['MAE_bps']))


def render_cover(route):
    from opening_animation import render_opening
    render_opening()
    st.markdown('''<style>
.research-hero{padding:22px 0 12px;border-top:1px solid #25344a}.hero-label{font:11px monospace;letter-spacing:.16em;color:#70b7ff}.hero-title{font-size:clamp(36px,5vw,64px);line-height:1.08;letter-spacing:-.045em;font-weight:650;margin:18px 0;color:#e5edf7}.hero-description{font-size:19px;line-height:1.55;color:#c1d0df;max-width:800px;margin:0 0 12px}.hero-purpose{font-size:14px;line-height:1.65;color:#91a7be;max-width:800px}.finding-value{font:600 clamp(29px,3vw,42px) monospace;letter-spacing:-.04em;color:#dcecff;margin:8px 0 14px}.finding-label{font:11px monospace;letter-spacing:.12em;color:#b8cde3;text-transform:uppercase}
</style><section class="research-hero"><div class="hero-label">01 / RESEARCH WORKSPACE</div><h1 class="hero-title">Stablecoin Stress Lab</h1><p class="hero-description">A price near $1 does not mean you can sell at $1.</p><p class="hero-purpose">A research lab for understanding how stablecoin sell-offs strain liquidity, trigger feedback loops, and challenge price forecasts.</p></section>''',unsafe_allow_html=True)
    st.subheader('Key Findings')
    f=findings();cols=st.columns(3)
    cards=[('Observed stress',f"${f['low']:.4f}",'USDC’s sampled low during the March 2023 SVB shock.',f"{f['quotes']} historical contract quotes reproduced within 0.000001 bps."),
           ('Daily forecasting',f"+{f['improvement']:.1f}%",'Lower overall daily MAE in one SVB evaluation; this is not a crisis-performance claim.',f"Fixed SVB evaluation: **{f['targets']} shared one-day targets**; only **{f['stress_targets']} stress target** (>100 bps). On that target GB error is 497.1 bps vs persistence 445.0 bps."),
           ('Hourly baseline shortfall',f"{f['covariate_improvement']:.1f}%",'GB + observed covariates versus persistence: lower is worse on this skill scale.',f"Price-only GB: {f['price_only_improvement']:.1f}%. Covariates reduce GB MAE by {f['ablation_gain']:.2f}%, but neither version beats persistence. 171 shared hourly targets, including 41 stress targets.")]
    for col,(label,value,text,note) in zip(cols,cards):
        with col:
            with st.container(border=True):
                st.markdown(f'<div class="finding-label">{label}</div><div class="finding-value">{value}</div>',unsafe_allow_html=True)
                st.write(text);st.caption(note)
    with st.expander('Finding definitions & evidence'):
        st.write('Observed low: hourly provider samples, March 9–15, 2023; not exchange OHLC. Solver accuracy: maximum absolute relative error over five historical blocks, three sizes and both USDC/USDT directions. Forecast improvement = 100 × (1 − model MAE / persistence MAE); daily and hourly experiments are separate.')
        st.markdown('[Data and contract benchmark]('+REPO+'/tree/main/stablecoin-stress-lab-streamlit/empirical_data) · [Research methods]('+REPO+'/blob/main/stablecoin-stress-lab-streamlit/EMPIRICAL_RESEARCH.md)')
    st.subheader('Try the mechanism')
    st.write('Try it: sell 40% of the pool and watch the quote fall.')
    from impact_animation import render_impact_animation
    render_impact_animation(show_heading=False)
    st.divider()
    def start_usdc_case():
        st.session_state['research_case']='USDC · March 2023'
        st.session_state.pop('case_snapshot',None)
        route('Historical Research')
    st.button('Start here: the USDC March 2023 case →',type='primary',on_click=start_usdc_case,width='stretch')
    with st.expander('New to the lab? Follow one question'):
        st.markdown('1. **Observe** the March 2023 price dislocation.\n2. **Inspect** the historical pool and its data sources.\n3. **Test** a sale and a liquidity assumption.\n4. **Check** model errors, validation and limitations.')
    st.subheader('About')
    st.markdown('**JIAYI ZHANG** · University of Macau\n\nI study accounting and am developing a quantitative research practice with an interest in C++ and computational finance. I built this lab to investigate a practical question: when a stablecoin trades near $1, how much can actually be sold near that price?\n\nThe project connects balance-sheet thinking with market microstructure, reproducible simulation, and honest model evaluation—including negative results.')
    st.caption('Research note: in preparation. A PDF link will be added when the note is available.')
    st.markdown('[GitHub]('+REPO+') · [Research methods & data]('+REPO+'/blob/main/stablecoin-stress-lab-streamlit/EMPIRICAL_RESEARCH.md) · [zhangjiayi419@gmail.com](mailto:zhangjiayi419@gmail.com)')
