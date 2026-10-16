# Research workspace update

## Navigation and presentation

The opening Overview combines a concise research statement, three direct task links and a pausable CSS mechanism illustration. It respects reduced-motion preferences and labels the animation as illustrative. It is an original design inspired by clear institutional positioning, not a copy of another firm's branding.

Forecast Lab provides comparable model evidence. Experiment Journal keeps the current session's latest 20 distinct runs and supports JSON exports; it is not a persistent account database. Liquidity, holdings, cohort and connected-mechanism experiments record submitted inputs and results.

## Forecast specification

All targets are last sampled daily USD observations, not exchange OHLC. At least 45 consecutive observations per asset are required; only the last 90 are used. The evaluation uses at most 20 expanding origins, each with at least 30 past observations, with all seven-day target endpoints observable. Horizons 1, 3 and 7 use the same origins. Metrics are endpoint MAE, RMSE and maximum absolute error in basis points of USD 1. The stress subset uses absolute realized peg deviations of at least 100 bps; an empty subset is not a successful stress test. Overlapping horizons produce dependent errors.

Models:
- Persistence: last value.
- Rolling mean: fixed mean of last seven observed days.
- AR(1): bounded coefficient [-0.98, 0.98], recursive point forecast.
- Gradient boosting: peg deviation target, lags 1/2/3/7, trailing 7d mean/std and last difference. Fixed 50 trees, depth 2, min leaf 5, learning rate 0.05, Huber loss and seed 419. No tuning on reported evaluation targets.
- Chronos-2: separately generated CPU inference artifact using exact model revision and package version. Univariate peg-deviation input; cross-learning disabled to prevent cross-origin future leakage. The artifact is included only when the cleaned dataset SHA-256 matches. Saved results do not automatically refresh when market data changes. See build_chronos_snapshot.py and requirements-research.txt. PyTorch and model weights are not runtime website dependencies.

Pretraining overlap is not independently audited. The evaluation establishes chronological inference inputs, not exclusion of test events from foundation-model pretraining. Point forecasts are not depeg probabilities, calibrated risk scores or evidence of trading profits.

## Research proposal

Co-TSFA is shown as an untrained research direction. The proposed experiment compares the same encoder with and without anomaly-oriented contrastive regularization, holds out complete stress events, separates normal/stress metrics and reports multiple seeds. No Co-TSFA result is fabricated.

Run: `python -m unittest discover -s tests -v`.
