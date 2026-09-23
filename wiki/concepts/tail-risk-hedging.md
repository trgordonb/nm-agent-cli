---
type: concept
title: "Tail risk hedging"
tags: [tail-risk, portfolio-allocation, hedging]
sources: [trend-following-tail-risk-hedging-alpha, trend-following-ctas-vs-arp-products, allocation-to-systematic-volatility-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Tail risk hedging

Allocations designed to protect against extreme downside markets. The wiki's regime-conditional framework sorts candidate hedges into **defensive strategies** (negative marginal bear beta bought with negative risk-premia alpha — insurance that costs carry) versus the trend-following anomaly (negative bear betas with insignificant alpha cost) — see [[regime-conditional-beta]] and [[risk-premia-alpha]].

## Evidence on candidate hedges

- **Long-vol funds:** positive skew but no positive convexity; tail-risk funds: skew and convexity but strongly negative overall performance. Neither is satisfactory ([[trend-following-tail-risk-hedging-alpha]]).
- **Trend-following CTAs:** positive convexity *and* positive performance; conditional on the worst S&P 500 quarterly quintiles they generate significant positive returns with positive skew. As an allocation: 50/50 with HFR risk-parity funds halves drawdown at equal Sharpe, because drawdown occurrences are independent.
- **Filtered L/S VIX carry:** negative correlation/beta to SPY, TLT, and 50/50 benchmarks in 2005–2017 — a carry strategy doubling as a diversifier ([[allocation-to-systematic-volatility-strategies]]), though its short-vol core carries the opposite tail exposure when the filter fails (the XIV caution in the source's open questions).

## Hedging via rule removal

Alvarez's contribution is defensive *within* a timing strategy: the 2022 stock-bond joint bear market showed TLT is not an unconditional hedge ([[stock-bond-correlation]], [[spy-sso-tlt-strategy]]) — adding a TLT-below-MA → cash rule "has a huge impact on MDD with only a slight change in CAR."
