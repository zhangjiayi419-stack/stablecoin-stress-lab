# Historical archive integration — 2026-10-21

- Historical Research now opens with an exact-block archive (843 states; three event windows).
- 662 blocks are new relative to the original 73-state replay catalog and 346-state empirical collection; 181 overlap. Counts are not additive independent evidence.
- Event/date/block controls use actual UTC timestamps and stable event-specific state keys.
- Each selected block supports pool-composition inspection and a USDC→USDT exact-input estimate using that same block's balances, A and fee. It does not feed the participant model or invent a USD market price.
- Full data, new-only CSV, raw RPC responses, block hashes, collection scripts and validation metadata are published. The six independent provider checks remain available.
- Data & Contract Evidence and data-scope reconciliation expose the new collection separately. Daily Brief market context displays the expanded archive count.
- Existing forecast scores, the SVB price-path fit and all original simulation anchors stay fixed for reproducibility. No behavioral calibration or forecast retraining is claimed.
- Desktop project source is unchanged. Desktop collection is copied read-only into this release.
