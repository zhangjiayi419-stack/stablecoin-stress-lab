# A five-block first visit

The landing page now leads with a skippable 4.2-second fixed-depth illustration, followed by a plain-language hero, three sourced findings, the retained order-impact widget, and one case-study entry plus About. The opening is gated by `_home_intro_seen` in Streamlit session state; reduced-motion visitors go directly to its closing line. It is explicitly synthetic, not an SVB replay.

The three finding values are read from executed data: USDC sampled low 0.876675; gradient-boosting daily SVB MAE improvement 23.0389% on 55 common targets; hourly observed-covariate improvement -59.77% relative to persistence. These are different experiments, with definitions in the evidence expander. The 30 historical solver comparisons have maximum measured error below 0.000001 bps. The unverified suggested 35% improvement is not used.

The interactive order widget defaults to 40% and retains its Play/Pause/Reset controls. The primary button always opens the USDC March 2023 historical case, including after a visitor has previously selected a USDT case. The four-step guide is collapsed. The redundant navigation cards, Daily Brief teaser, separate SVB teaser, market cards, and 30-day chart are removed from Overview. Market cards and the chart are now in Daily Brief.

About uses the owner's supplied public name, institution and email, plus GitHub and research-method links. No paper or affiliation details beyond the supplied information are invented.
