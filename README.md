# Stablecoin Stress Lab

A research workspace for understanding stablecoin price dislocations and liquidity under stress. The central question is how a hypothetical sale would execute in a recorded Curve 3pool state, and how an explicit change in pool depth changes the estimate.

[Open the live Streamlit application](https://stablecoin-stress-lab-bocqwkh5biv65pbodvlaqz.streamlit.app/)

## Four workspaces

| Workspace | Research question | Tools |
| --- | --- | --- |
| Overview | What do the latest observations show? | Dated USD snapshots, 30-day deviation chart, English daily brief and a guided entry point |
| Historical Research | What happened during a stress event? | Three curated cases, daily USD prices, sparse pool-composition observations and source trails |
| Liquidity Stress Test | How does a sale or explicit shock change the model output? | USDC/USDT sale estimates, proportional liquidity counterfactuals, holdings scenarios and optional participant sensitivity experiments |
| Models & Validation | What evidence supports the estimate? | Chronological AR(1) vs persistence evaluation, model specifications, validation gaps, provenance and research roadmap |

The interface separates observed data, estimates conditional on historical pool states, and hypothetical scenarios. Advanced controls and raw exports are available without dominating the beginner workflow.

## Run locally

Python 3.10 or newer is required. From the repository root:

```bash
cd stablecoin-stress-lab-streamlit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Data and interpretation

Recent USD observations use CoinGecko, with the last sampled observation in each completed UTC day. The bundled historical USD series uses hourly observations aggregated by UTC day; sampled lows and daily last observations are different measures. Neither is exchange OHLC.

The 73 stored Ethereum Curve 3pool snapshots carry actual block timestamps and source metadata. Missing dates are not interpolated. Pool balances are token quantities, not dollar-valued reserves. Pool-block times and daily USD prices are not synchronized.

## Models and evidence

- **Execution:** a floating-point three-token StableSwap solver, with recorded A, balances and fees. Numerical checks cover gross-output invariant preservation, fee arithmetic, scaling and trade-size/depth sensitivity. Agreement with archived contract `get_dy` outputs and realized transactions remains unvalidated.
- **Scenarios:** rule-based holder cohorts, issuer processing, arbitrage and liquidity withdrawals. Parameters are explicit and uncalibrated. USDC/USDT holdings paths combine independent token simulations, not a joint market model.
- **Forecast research:** a fitted AR(1) baseline with one-day expanding-window evaluation against persistence. Conditional 90% residual-bootstrap intervals omit parameter uncertainty; multi-day coverage has not been independently validated. No predictive superiority is assumed.
- **JEPA:** a research proposal, not a trained or deployed model.

## Daily English brief

GitHub Actions refreshes the saved price snapshot and brief at 01:15 UTC (09:15 Asia/Shanghai; scheduling may be delayed). Configure `DASHSCOPE_API_KEY` in repository Actions secrets for optional Alibaba Qwen commentary. When unavailable, the report explicitly uses a deterministic English statistical template. Failed market-data updates preserve the previous dated report.

The public app reads saved reports. Visitors cannot trigger paid model calls with the owner's credentials. Setup details are in [START_HERE.md](stablecoin-stress-lab-streamlit/START_HERE.md).

## Checks

```bash
cd stablecoin-stress-lab-streamlit
python -m unittest discover -s tests -v
```

Research prototype. The application does not execute trades, estimate a calibrated probability of safety, or provide statistical VaR. Scenario losses, original-pool sale estimates and historical price observations have distinct meanings.
