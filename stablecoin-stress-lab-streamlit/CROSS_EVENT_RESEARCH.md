# Forward event transfer study

Retrospective research software by Jiayi Zhang, University of Macau. Events and model families were previously inspected; this is not preregistered prospective validation.

## Observations

431 aligned hourly feature rows cover Terra (144), FTX (144), and SVB (143), using 435 exact-block state cutoffs, 435 block base-fee headers, and 88,031 Curve 3pool event logs. New collection adds 1,152 price samples and 51,299 Terra/FTX logs from 288 complete hourly intervals. SVB sources are reused and fingerprinted, not independent new evidence. Six swap logs reconcile against receipts from the same RPC provider.

USD prices are sampled provider observations, not exchange OHLC or executable prices. Missing/stale samples are excluded. Target samples already known at forecast origin are excluded. No interpolation. Single-coin withdrawal amounts are not assigned an unknown token: only counts enter the model. Gas is block base fee, not transaction gas paid. Invariant decline is a confounded proxy, not identified participant behavior.

## Fixed evaluation

Train Terra → test FTX; train Terra + FTX → test SVB. One-hour horizon. Persistence is the zero-price-change null. Price-only GB and GB plus eight observed covariates use identical eligible targets within each asset/fold. Hyperparameters and seed 419 are fixed in `cross_event_study/protocol.json`. Last 32 training examples calibrate a frozen nominal 90% residual interval; model fitting uses only preceding examples. No test-event refitting, tuning, or interval feedback.

| Asset / test | Targets | Persistence MAE bps | Price-only GB MAE | Covariate GB MAE | Covariate skill vs persistence | Covariate coverage |
|---|---:|---:|---:|---:|---:|---:|
| USDC / FTX |109|31.4152|27.0606|26.8967|+14.3833%|69.7248%|
| USDC / SVB |74|50.1023|188.2501|212.0231|−323.1801%|50.0000%|
| USDT / FTX |105|27.0361|22.7110|25.7422|+4.7859%|80.9524%|
| USDT / SVB |83|18.4074|30.9270|33.7449|−83.3228%|78.3133%|

Overall improvement does not imply better stress-subset prediction: USDC FTX has only four stress targets and covariate stress MAE 83.6061 bps exceeds persistence 82.7341 bps. Full RMSE, maximum error, stress metrics, widths and Winkler scores are exported. Crisis shift can invalidate nominal interval coverage; observed failures are retained.

## Reproduce

From the app directory, install `requirements-lock.txt`, then run:

```
python build_cross_event_study.py
python -m unittest discover -s tests -q
python verify_release.py
```

Rebuilding uses packaged frozen inputs and does not require new network calls. `collect_cross_event.py` recollects public APIs and produces a new dataset version; it is not needed to reproduce results. Raw JSON-RPC/price responses are retained in four gzip JSONL shards; request/source hashes, coverage exclusions, calibration residual predictions and all test predictions are exported. Build timestamps may differ while the fixed input hashes and model results remain the reproducibility reference.

Only one pool and two forward test events are studied. Assets/folds are not independent replications. These results do not establish causal mechanisms, trading profitability, structural ABM calibration, or general cross-pool validity. Earlier daily and SVB-only studies remain separately labeled and retain their own target populations.
