# Mechanism Lab — assumptions and validation

This workspace adds a synthetic two-token sandbox alongside the historical Curve 3pool estimator. It does not replace recorded historical data with simulated observations.

- AMMs: two-token Curve StableSwap, fee-adjusted constant product, and piecewise concentrated liquidity across tick-aligned boundaries. Equal starting marked value; 4 bps pool fee. v3 positions allocate 80% to the inner range and 20% to ±2000 ticks. Unfilled volume is exposed, with fees charged only on fills.
- LP response: discount trigger, response coefficient and withdrawal momentum; proportional withdrawals bounded by a configured maximum. Existing cohort ABM LP withdrawal now works independently of Treasury mode.
- Arbitrage: finite cash, positive expected net proceeds after gas and financing, delayed redemption and capital recycling. Redemption value is assumed, not predicted; no issuer capacity is modeled in this new sandbox.
- Liquidation: editable synthetic single-collateral accounts, USD debt, lagged DEX-linked oracle, health factor below one, configured close factor and bonus, finite working capital, profitable full collateral sale required. Actual protocol eligibility, bad debt, oracle designs and account distributions are not reproduced.
- Recovery: first sample after the trough within ±1% of USD 1 for five consecutive samples. No recovery within the horizon is reported explicitly.
- Charts: Plotly with crosshair spikes, unified hover, zoom and SVG export. Transparent chart surfaces share the dark terminal palette. Existing pages and daily brief remain accessible.

Run `python -m unittest discover -s tests -v`. Numerical and accounting tests cover invariants, tick crossing and exhausted ranges, proportional LP withdrawal, health-factor thresholds, zero-capital behavior, position/debt accounting, finite capital and determinism. These checks do not constitute onchain calibration or predictive validation.

References: [Curve](https://docs.curve.finance/developer/amm/legacy/stableswap-overview/), [Uniswap v3](https://app.uniswap.org/whitepaper-v3.pdf), [Aave](https://aave.com/faq).
