---
type: concept
title: "Look-ahead bias"
tags: [backtest, research-methodology, overfitting]
sources: [historical-volatility-parameter-adjustment, allocation-to-systematic-volatility-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Look-ahead bias

Contaminating a backtest with information not available at decision time. The clean demonstration in this wiki: the SPX timing strategy's HV cutoff (17) was calibrated as the 80th percentile of *full-history* data. In 1975 no trader could have known that value. Recomputing the percentile point-in-time — the honest version — collapsed results to buy-and-hold ([[historical-volatility-parameter-adjustment]]).

## Forms seen across sources

- **Calibration leakage:** static thresholds fitted on the full sample (above).
- **Data-driven rule choice:** Alvarez's recurring discipline of re-testing published rules on recent windows precisely because their parameters were chosen on older ones ([[parameter-robustness]]).
- **Model fitting at roll time:** Sepp's [[statistical-filtering]] is the positive example — the time-series model uses data *strictly prior* to each roll, and [[volatility-targeting]] likewise computes trailing vol strictly before rebalancing ([[allocation-to-systematic-volatility-strategies]]).

## The subtler variant

Unconditional performance aggregation is a soft look-ahead: knowing the whole sample's regime mix before judging a "market-neutral" product. Regime-conditional evaluation is the cure ([[regime-conditional-beta]]).
