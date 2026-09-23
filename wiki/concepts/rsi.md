---
type: concept
title: "RSI(2) mean-reversion engine"
tags: [mean-reversion, technical]
sources: [volume-and-mean-reversion]
created: 2026-09-23
updated: 2026-09-23
---

# RSI(2) mean-reversion engine

The 2-period Relative Strength Index as a short-horizon mean-reversion trigger: enter when RSI(2) < 1 (extreme oversold), exit when RSI(2) > 70. It is the machinery underneath Alvarez's volume study — Russell 3000, close > $3, 21-day dollar-volume floor, next-open execution ([[volume-and-mean-reversion]]).

## Notes

- Used here as a *baseline engine* whose signals are then modified (volume percent-rank), not as the object of study itself; no standalone parameter scan of RSI(2) exists in the ingested sources.
- The engine's trade quality interacts with regime: above the 200-day MA it averages +0.54%/trade vs +0.15% below — see [[mean-reversion]].
