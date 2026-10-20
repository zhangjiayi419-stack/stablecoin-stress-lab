"""Explicit estimands, evidence scope, clocks and reproducibility contract."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parent
REPO='https://github.com/zhangjiayi419-stack/stablecoin-stress-lab'

def scope_rows():
    from backend.app.services.replay import load_pool_state
    states=json.loads((ROOT/'empirical_data/pool_states.json').read_text())
    replay=load_pool_state()
    return [dict(Collection='Empirical Curve 3pool states',Count=len(states),Unit='State records; mixed daily/hourly requested cutoffs',Scope='Jan–Apr 2023; separate empirical collection; repeated block cutoffs may occur'),
            dict(Collection='Historical replay catalog',Count=len(replay),Unit='Sparse pool state records',Scope='2021–2026; case pages filter this catalog by dates'),
            dict(Collection='SVB case replay subset',Count=sum('2023-03-09'<=s['timestamp'][:10]<='2023-03-15' for s in replay),Unit='Catalog records in selected case window',Scope='Subset of replay catalog, not additional observations'),
            dict(Collection='Exact-block contract checks',Count=30,Unit='Quotes = 5 blocks × 3 order sizes × 2 directions',Scope='Numerical solver validation only; not 30 independent crisis events')]

def render_scope():
    with st.expander('Evidence scope & count reconciliation',expanded=False):
        st.warning('Single-pool microstructure evidence. SVB participant path is fitted in-sample. The response estimator fails its chronological holdout against the zero-response null. No externally validated structural behavior or calibrated default probability is claimed.')
        st.table(pd.DataFrame(scope_rows()))
        st.table(pd.DataFrame([
            {'Study':'SVB price-path fit','Across events':'No','Across pools':'No','Conclusion':'In-sample effective scenario, not structural identification'},
            {'Study':'Hourly covariate ablation','Across events':'No: Mar 7–17 2023','Across pools':'No: Curve 3pool','Conclusion':'Covariates slightly help GB; both GB versions lose to persistence'},
            {'Study':'Retrospective daily event audit','Across events':'Terra May 2022; FTX Nov 2022; SVB Mar 2023','Across pools':'Not applicable: USD samples only','Conclusion':'Chronological forecast robustness check; not preregistered and not ABM external validation'},
            {'Study':'Multi-pool / event-held-out ABM','Across events':'Not completed','Across pools':'Not collected','Conclusion':'External validity remains unestablished'}]))

def render_event_audit():
    path=ROOT/'empirical_data/event_audit.json'
    if not path.exists():return
    data=json.loads(path.read_text())
    st.subheader('Retrospective event robustness audit')
    st.write(data['scope'])
    event=st.selectbox('Audit event',[r['event'] for r in data['events']],key='external_event_audit')
    result=next(r for r in data['events'] if r['event']==event)
    from empirical_ui import score_table
    score_table(result['scores'])
    st.caption(f"Only targets inside {result['start']} → {result['end']} UTC are scored. 120 pre-event daily samples supply training/residual warm-up; rolling fits see only prior targets. Fixed one-day horizon, identical origins across all five models. Daily closes can miss intraday depegs. Seed 419. No event selection is based on model rank.")
    st.download_button('Download complete event audit',json.dumps(data,indent=2),'event-robustness-audit.json','application/json')

def render_standards():
    st.subheader('Research contract · definitions, scope and citation')
    render_scope()
    st.markdown('**Estimands.** USD peg deviation, executable recovery and issuer default describe different outcomes. All stress labels below are measurement conventions, not credit ratings.')
    st.latex(r'd_t=10^4(P_t^{USD}-1),\qquad S_t=\mathbf{1}\{|d_t|>100\}')
    st.caption('Two-sided >100 bps sampled deviation is a forecast scoring subset. Report sign, sampling frequency, horizon and stress-target count; it is not an issuer-default event. Intraday sampled lows and daily last observations are separate estimands.')
    st.latex(r'D_{t,H}=\mathbf{1}\{\text{contractual redemption obligation unpaid by }t+H\},\quad PD_{t,H}=\Pr(D_{t,H}=1\mid\mathcal F_t)')
    st.latex(r'LGD_H=1-\frac{\operatorname{PV}(\text{recovery cash flows})}{EAD},\qquad EL=PD_{t,H}\,\mathbb E[LGD_H\mid D_{t,H}=1]EAD')
    st.write('Issuer PD/LGD require redemption obligations, due dates, recoveries and discount assumptions. These data are absent: issuer PD, LGD and expected credit loss are **not estimated**. A below-par market price alone is not default. Any optional seeded credit hazard is a user-specified scenario probability, not an estimated issuer PD.')
    st.latex(r'\ell_{exec}(q,t)=1-\frac{\text{net USD output}(q,t)}{q\cdot 1\mathrm{USD}}')
    st.caption('Execution shortfall is conditional on order size, block, route and fees. It can be negative for a premium and must not be labeled LGD. Simulated quote moves are in percentage points of USD 1; percentage returns use the initial quote as denominator.')
    st.markdown('**Clocks.** State: exact block at/before cutoff. Features: interval ending at cutoff, using information then available. Forecast: origin precedes target; residuals update only after resolution. Latest feed and frozen model snapshot may have different cutoffs; generation time is recorded separately.')
    st.markdown('**External-validity gate.** Before claiming calibrated behavior: collect another pool and complete non-SVB events, freeze model/tuning rules before scoring, split by entire event, compare zero-response and persistence, report sensitivity and uncertainty. Current retrospective event audit broadens forecast evidence only.')
    st.markdown('**Bibliography**\n\n1. Egorov (2019), [StableSwap](https://docs.curve.fi/assets/pdf/whitepaper_stableswap.pdf).\n2. Adams et al. (2021), [Uniswap v3 Core](https://app.uniswap.org/whitepaper-v3.pdf).\n3. Gibbs & Candès (2021), [Adaptive Conformal Inference Under Distribution Shift, NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html). The bounded finite-quantile implementation here differs from the theoretical algorithm; no per-event guarantee is asserted.')
    st.markdown('**How to cite.** Zhang, Jiayi (2026). *Stablecoin Stress Lab: evidence audit*. Research software, v0.4.0-evidence-audit. Cite the release commit and dataset fingerprint used; this is software, not a peer-reviewed paper.')
    for name in ['CITATION.cff','LICENSE','REPRODUCIBILITY.md','requirements-lock.txt','release_manifest.json']:
        path=ROOT/name
        if path.exists():st.download_button('Download '+name,path.read_bytes(),name,key='research_contract_'+name)
    st.caption('Code: MIT. Third-party datasets retain source terms; the code license does not relicense provider data. Source and artifact SHA-256 hashes identify the exact local release contents; reproduce from the tag and verify before rerunning. Runtime lock: CPython 3.13; hosted runtime can differ.')
