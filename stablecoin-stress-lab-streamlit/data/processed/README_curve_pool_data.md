# Curve 3pool snapshot input

The app needs real, timestamped Curve 3pool balances before it can calculate a historical quote. No pool balances were present in this project when the backend was added, so the app deliberately reports quotes as unavailable until this dataset is imported.

Download the CSV template from the experiment panel. Required columns:

`timestamp,dai_pool,usdc_pool,usdt_pool,amp,fee_rate,source,method`

- `timestamp`: UTC ISO 8601 timestamp, e.g. `2023-03-11T12:00:00Z`.
- `dai_pool`, `usdc_pool`, `usdt_pool`: human token quantities at that block (not raw integer contract units).
- `amp`: the A value returned by the Curve 3pool `A()` getter. The model uses the same coefficient directly; do not apply another precision conversion.
- `fee_rate`: fee fraction, e.g. `0.0004` for 0.04%.
- `source`: URL, archive node reference, query ID, or other auditable provenance.
- `method`: how the block and balances were sampled.

Importing through the page saves the CSV as `data/processed/curve_3pool_balances.csv`. Imported rows merge by timestamp; an uploaded row replaces a stored row at the same timestamp and other dates are preserved. Quotes only use a snapshot from the selected UTC calendar date; the UI does not interpolate missing pool states. The UI displays the matched snapshot timestamp and whether its metadata identifies an on-chain JSON-RPC read. Provenance metadata is not an independent audit of the RPC provider.

Balance snapshots and parameter values must refer to the same Ethereum block. Verify the pool address, token decimals, A precision, fee precision, and timestamp alignment before using an estimate. The quote is a simplified static StableSwap model, not an executable Curve quote.

## Expand the daily history

Run `scripts/fetch_curve_3pool.py` with inclusive start and end dates to fetch daily snapshots near 16:00 UTC and merge them into the existing CSV:

```sh
ETH_RPC_URL=https://eth-mainnet.public.blastapi.io python3 scripts/fetch_curve_3pool.py 2021-10-07 2026-10-06
```

Use an archive-capable Ethereum RPC endpoint you trust. Public endpoints may rate-limit or require a key. Each successfully fetched range is saved, and existing dates remain untouched if a later fetch fails. `curve_3pool_manifest.json` records the exact available dates and sources. Each snapshot stores its actual block timestamp and is selected no more than 300 seconds before 16:00 UTC.

For a broad five-year baseline using fewer public-node requests, run `ETH_RPC_URL=https://eth.drpc.org python3 scripts/fetch_curve_3pool.py --monthly`. This stores monthly reference dates plus selected stress-event dates. Dates without snapshots remain unavailable to exact-date quotes; no pool values are interpolated.

## Agent scenario

`POST /api/agents/simulate` runs a deterministic hourly counterfactual from an exact-date historical snapshot. It exposes holder sell intent, panic, redemption cost and share, issuer delay and capacity, arbitrage response, and an initial pool liquidity adjustment. Redemption requests not processed within six hours after their modeled due time return to pool selling. Independent daily USD references are held fixed throughout the run because intraday references are not available across the full history. Results are hypothetical and do not predict real agent actions, issuer reserves, or future prices.
