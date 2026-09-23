---
type: concept
title: "Convexity (return profile)"
tags: [performance-measurement, tail-risk, trend-following]
sources: [trend-following-tail-risk-hedging-alpha, trend-following-ctas-vs-arp-products]
created: 2026-09-23
updated: 2026-09-23
---

# Convexity (return profile)

The curvature of a strategy's returns with respect to its benchmark: a **positively convex** strategy gains more than linearly in extreme benchmark moves in either direction. Together with skewness, convexity is Sepp's key metric for the risk profile of quant strategies ([[trend-following-tail-risk-hedging-alpha]]).

## The landscape (Eurekahedge indices)

| Strategy type | Skewness | Convexity | Overall performance |
| --- | --- | --- | --- |
| Long-vol funds | Positive | Absent | — |
| Tail-risk funds | Significant | Significant | Strongly negative |
| Short-vol funds | — | Significantly negative | — |
| Trend-following CTAs | Positive | Significant positive | Positive |

Trend-followers are the only category combining positive convexity with positive overall performance — the quantitative case for them as diversifiers ([[crisis-alpha]], [[tail-risk-hedging]]).

## Measurement subtleties

- Convexity appears only when the return measurement period exceeds the trend smoothing half-life plus rebalancing period — short measurement windows hide it ([[trend-following-tail-risk-hedging-alpha]]).
- The mirror image: [[delta-hedging]]-style short-gamma strategies show small normal-regime beta but negative convexity that regime-conditional analysis surfaces as crisis beta ([[trend-following-ctas-vs-arp-products]]).
- Equity momentum has negative convexity; trend-following positive — the same adaptive logic, opposite curvature ([[trend-following]]).
