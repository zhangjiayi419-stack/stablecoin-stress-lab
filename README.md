# Stablecoin Stress Lab

An interactive research prototype for exploring stablecoin market stress, pool liquidity, and hypothetical participant behavior.

Built with Python and Streamlit, the application combines historical observations with clearly labeled stress simulations.

## Features

- **Portfolio Stress Check** — Enter USDC and USDT holdings and explore hypothetical mark losses.
- **Scenario Presets** — Explore reserve freezes, redemption pressure with LP withdrawals, and interest-rate shocks.
- **Historical Replay** — Compare independent USDC/USD and USDT/USD price observations.
- **Pool & Slippage** — Estimate USDC-to-USDT execution using sourced historical Curve 3pool snapshots.
- **ABM Sandbox** — Explore redemption pressure and pool depth through an interactive phase diagram.
- **Interactive Agents** — Configure retail holders, institutions, arbitrageurs, issuer queues, yield-driven holders, and strategic LPs.
- **Risk Assistant** — Run a deterministic analysis workflow with readable explanations and audit records.
- **Report Export** — Download scenario results, assumptions, and source metadata as CSV.

## Data

The project includes:

- Historical USDC and USDT USD price observations aggregated by UTC day.
- Sparse Ethereum Curve 3pool snapshots with recorded block identifiers and timestamps.
- Curated references for selected market stress events.

Data provenance is documented in:

- `data/manifest.json`
- `data/processed/curve_3pool_manifest.json`
- `data/processed/macro_event_sources.csv`

Historical prices and pool snapshots may differ in observation time. Daily sampled highs and lows are not exchange OHLC data.

## Models

### Pool execution

A numerical Curve StableSwap solver estimates trade output, fees, and price impact from historical pool balances and parameters.

### Market participant simulation

A discrete hourly model represents:

- Finite retail selling pressure.
- Institutional redemption requests.
- Capital-constrained arbitrage.
- Issuer processing delays and cash availability.
- Yield-driven redemptions.
- Risk-sensitive liquidity withdrawals.

Optional Treasury-token scenarios introduce hypothetical reserve freezes, collateral impairment, interest-rate changes, and duration exposure.

### Risk analysis workflow

The Risk Assistant coordinates data checks, numerical calculations, interpretation checks, and template-based reporting.

It is inspired by financial-agent orchestration research but does not use an LLM or execute trades.

### Forecasting research

The JEPA section describes a proposed forecasting experiment. No trained forecasting model or predictive service is included.

## Run Locally

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
