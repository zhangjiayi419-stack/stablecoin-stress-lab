# Matched scenario comparison and date-only forecast charts

The reported 15% scenario mismatch was reproduced. The visible path used the March 10 pool state and fitted arbitrage capital of approximately USD 98.9m. The old preloaded sensitivity artifact used March 11 and different behavioral assumptions. Rendering the retained grid beside the current path allowed a misleading comparison.

The new path and grid share the full submitted request. All non-axis parameters remain identical; current pressure/depth coordinates are explicitly simulated, even when absent from the original grid. The selected cell is marked and numerically checked against the path. Both plots update together; cached old canonical grids are not substituted. Exported requests include a shared SHA-256 identifier. The grid uses categorical cells, so colors do not imply an interpolated cliff at an untested pressure.

For the reference-derived March 10 scenario at 15%, the initial pool-implied quote is 1.001013514, the ending quote is 1.000137613, maximum move from initial is 0.087590101 percentage points, and maximum discount below USD 1 is zero. Quotes use the pool's marginal USDC/USDT exchange rate multiplied by a fixed USDT/USD reference of 1.001. This cross-rate translation is not an observed independent USDC/USD price path. A sale may reduce a premium without producing a discount. The simplified redemption arbitrage is discount-side only; premium-side issuance arbitrage is not represented, and prices are not artificially clipped at par.

Models & Validation now uses explicit ISO date category ticks. A one-day projection uses forecast and persistence markers with an asymmetric conditional-interval error bar, avoiding Plotly's expansion of a lone midnight date into sub-millisecond ticks. Three- and seven-day horizons retain dated paths and shaded intervals.

Checks include the exact reported 15% request, equality of path and selected-cell metrics, rejection of mismatched requests, evaluation of non-grid depth coordinates, frozen reference consistency, explicit date ticks for all horizons, and single-point error bars.
