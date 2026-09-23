---
type: concept
title: "Crisis alpha"
tags: [tail-risk, regime-analysis, trend-following]
sources: [trend-following-tail-risk-hedging-alpha, trend-following-ctas-vs-arp-products, allocation-to-systematic-volatility-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Crisis alpha

Positive performance delivered specifically during market stress — the property that makes a diversifier worth holding despite drag in normal times. The wiki documents two distinct mechanisms for producing it:

1. **Adaptive positioning (trend-following):** with a smoothing half-life shorter than the crisis duration, trend systems flip short during sustained declines. Evidence: significant positive returns with positive skew conditional on the worst S&P 500 quarterly-return quintiles ([[trend-following-tail-risk-hedging-alpha]]); negative marginal bear betas under the regime-conditional model ([[trend-following-ctas-vs-arp-products]]).
2. **Direct short-volatility inversion:** the filtered long/short VIX-futures variant produced *negative* correlation and beta to all three benchmarks (SPY, TLT, 50/50) in Sepp's 2005–2017 backtest ([[allocation-to-systematic-volatility-strategies]]) — crisis alpha from a carry strategy whose hedge leg goes long volatility in backwardation.

## Boundary conditions

- Trend-following crisis alpha requires the crisis to persist (roughly ≥2 months) for positions to adapt; rapidly reversing crashes defeat it — the stated reason trend-followers also lost (less) in 2018 [[trend-following-ctas-vs-arp-products]].
- Long-vol funds have positive skew but *no* positive convexity; only trend-followers combine convexity with positive overall performance [[trend-following-tail-risk-hedging-alpha]].

## Related

[[convexity]] is the measurable signature; [[tail-risk-hedging]] is the allocation use-case.
