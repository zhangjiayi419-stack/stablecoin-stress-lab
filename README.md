# Stablecoin Stress Lab

An academic research workspace for stablecoin price dislocations, execution depth,
and explicit multi-cohort liquidity scenarios. Author: **Jiayi Zhang, University of Macau**.

[Open the Streamlit app](https://stablecoin-stress-lab-bocqwkh5biv65pbodvlaqz.streamlit.app/)

## Evidence before claims

- Daily SVB full-window gradient boosting MAE skill +23.0%: **55 shared targets,
  only one >100 bps stress target**. On that target GB error is 497.1 bps versus
  persistence 445.0 bps. This is not evidence of superior crisis forecasting.
- Hourly GB + observed covariates skill −59.8% versus persistence; price-only GB
  −62.2%. Covariates reduce GB MAE by about 1.48%, but both versions lose.
- New executed retrospective daily audits cover Terra May 2022, FTX November 2022
  and SVB March 2023 using identical rolling specifications and event-only scoring.
  This is post-hoc historical analysis, not preregistered external validation.
- Exact-block StableSwap checks: 5 blocks × 3 sizes × 2 directions = 30 historical
  contract `get_dy` quotes; maximum relative error below 0.000001 bps for tested cases.
- The participant SVB price path is fitted **in-sample**. Structural ABM behavior
  and generalization across pools/events remain unvalidated.
- Effective-response holdout MAE **0.17945 pp** versus zero-response null
  **0.08342 pp**: failed validation. The fitted coefficients are not deployed as
  calibrated participant behavior.

## Data scopes and clocks

The empirical collection contains 346 Curve 3pool state records during Jan–Apr
2023 (daily plus crisis-hourly cutoffs); the separate replay catalog contains 73
sparse historical state records. Case counts are filtered subsets of the replay
catalog, not conflicting estimates of the same population. Provider USD samples,
block state, event intervals and forecast targets use separate explicit clocks.

No issuer PD/LGD is estimated. The >100 bps two-sided peg-deviation label is a
sampled market stress convention, not issuer default. Execution shortfall is
order- and block-specific, and is not LGD.

## Reproduce and cite

Use tag **v0.4.0-evidence-audit**, CPython 3.13, and the pinned runtime environment.

```sh
cd stablecoin-stress-lab-streamlit
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
.venv/bin/python verify_release.py
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python build_event_audit.py
.venv/bin/python -m streamlit run streamlit_app.py
```

[Full reproduction protocol, limitations and bibliography](stablecoin-stress-lab-streamlit/REPRODUCIBILITY.md)
· [CITATION.cff](CITATION.cff) · [MIT code license](LICENSE)

Seeds: 419 for forecasting/bootstrap builders; ABM runs expose their request seed
and SHA-256. Data hashes and source hashes are in the release manifest. Optional
foundation weights are not included in the runtime lock; their results are frozen
artifacts. Mutable daily market reports are excluded from the release hash set.

Third-party data retains provider terms. This research software does not execute
trades or establish future model performance. Contact: zhangjiayi419@gmail.com.
