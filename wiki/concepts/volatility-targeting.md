---
type: concept
title: "Volatility targeting"
tags: [volatility, portfolio-allocation]
sources: [allocation-to-systematic-volatility-strategies, trend-following-tail-risk-hedging-alpha, machine-learning-for-volatility-trading]
created: 2026-09-23
updated: 2026-09-23
---

# Volatility targeting

Rescaling a strategy's exposure so its realized volatility stays near a fixed annual target, using only information available at each rebalance. Sepp applies a 10% annual target in two steps: run the strategy unleveraged, then size the allocation using trailing volatility computed strictly prior to each roll date ([[allocation-to-systematic-volatility-strategies]]).

## Roles in this wiki

- **Comparability:** unleveraged vol differences are huge (put ~10%, strangle ~5%, VIX ~50%); targeting makes the three [[volatility-carry-strategies]] comparable and their allocation weights meaningful.
- **Allocation math:** with 10% of funds allocated to targeted vol strategies, portfolio alpha rises ~1% and Sharpe 10–20% across SPY/TLT/50-50 benchmarks.
- **Evaluation caveat:** [[machine-learning-for-volatility-trading]] cites Andrew Lo's result that optimizing a volatility model *inside* a vol-targeting strategy can manufacture 40x apparent outperformance — the targeting mechanism amplifies model-choice bias, so the volatility forecast quality is load-bearing (see [[volatility-forecasting]], [[overfitting]]).

## Open questions

- Sepp's sources use the technique but never document the target-choice sensitivity (is 10% special? does the result survive 8% or 15%?) — a natural robustness question in the spirit of [[parameter-robustness]].
