# Empirical research release

This release separates observed evidence, predictive evaluation, and stylized simulations. It does not guarantee that a complex model beats persistence or identify a fully calibrated multi-agent model.

## Dataset

Public Ethereum mainnet Curve 3pool observations (pool `0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7`) and DefiLlama USD price samples cover January 1–April 15, 2023. The release contains 7,522 hourly price observations, 346 exact-block pool states, 41,202 supported swap/LP events, and 239 aligned hourly feature rows. Five historical blocks supply 30 actual `get_dy` comparisons (two directions, three order sizes); five event records were independently checked against transaction receipts.

Sources: https://eth.drpc.org ; https://coins.llama.fi ; https://github.com/curvefi/curve-contract/tree/master/contracts/pools/3pool . Original public HTTP responses are preserved in `empirical_data/raw_responses.jsonl.gz`. The manifest records request clocks, retrieval time, exclusions, source identifiers, and SHA-256 fingerprints. The raw archive manifest separately fingerprints compressed files.

## Alignment and evaluation

State blocks and price observations never exceed their feature cutoff. Prices older than two hours are excluded. The missing USDT observation at 2023-03-11 21:00 UTC is excluded, and hourly target/lag windows crossing that gap are not interpolated. Interval-end USD-marked volume becomes available only at that cutoff and predicts the next cutoff.

Daily evaluation uses identical chronological origins for persistence, rolling mean, AR(1), SETAR, and gradient boosting. It reports MAE, empirical coverage, interval width, nominal-90% Winkler score, and strictly greater-than-100-bps stress targets. Conformal residuals enter calibration only after their target is observed. Bounded ACI is an empirical adaptive procedure, not a finite-sample crisis coverage guarantee. The separate hourly covariate ablation has 171 common targets per asset; its models remain behind persistence and those results are retained.

## Execution and behavioral evidence

The maximum absolute relative error over the 30 historical float64 StableSwap/get_dy comparisons is 8.324991084862356e-7 bps. This is a measured sample result, not a universal solver accuracy bound. Narrow-range v3 execution explicitly stops when sell-side liquidity is exhausted and reports unfilled orders.

The response estimation is a constrained least-squares/minimum-distance fit of an effective net invariant withdrawal proxy, with chronological holdout and moving-block bootstrap. Fees and amplification changes confound that proxy. These coefficients are not causal participant preferences and are not substituted into the stylized ABM as identified structural parameters. Canonical journal entries come from actual solver and simulation executions, including a 42-cell sensitivity grid.

## Reproduce

Use Python with the application requirements and `requirements-research.txt` installed, then from this directory run:

```sh
python collect_empirical.py
python empirical_processing.py
python build_research_artifacts.py
python -m unittest discover -s tests -q
streamlit run streamlit_app.py
```

Collection uses public endpoints and resumable raw caches; endpoint availability can change. Precomputed JSON and gzip artifacts allow the website to render without live archive RPC access. Chronos remains a separately labeled univariate foundation-model baseline. No JEPA or cross-attention prototype is represented as a trained empirical result.

## Limits

One pool and one crisis do not establish out-of-event generalization. Provider price samples are not exchange OHLC. Single-coin withdrawal events do not contain a token identifier, so their USD value is not invented. The homepage animation is an illustrative fixed-depth mechanism demonstration. The partial response fit does not calibrate every behavioral parameter.
