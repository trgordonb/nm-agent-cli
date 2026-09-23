---
type: concept
title: "Trade selection (filtering vs ranking)"
tags: [research-methodology, trade-selection]
sources: [volume-and-mean-reversion, benford-law-strategy-selection]
created: 2026-09-23
updated: 2026-09-23
---

# Trade selection (filtering vs ranking)

Two ways to act on a signal-quality indicator: **filter** (drop setups failing the test) or **rank** (prefer setups passing the test when capacity is constrained). The volume study supplies the direct comparison ([[volume-and-mean-reversion]]):

| Approach | Trade count | Effect |
| --- | --- | --- |
| Filter (`PercentRank(V,20) < 20`) | Exposure 25% → 5% | Avg P/L 1.87% → 2.58%; fewer trades carry the edge |
| Rank (prefer low-volume signals) | ~unchanged | Small broad gains: CAR, UI, avg P/L, win rate, Sharpe |

## Generalization

Filtering concentrates capital in the edge but sacrifices compounding breadth; ranking preserves breadth at the cost of diluted per-trade improvement. The right choice depends on whether the *portfolio* or the *signal* is the scarce resource. Alvarez's own decision — adopt neither — adds the third axis: any selection rule must clear the complexity budget ([[parameter-robustness]]).

The failed Benford detector was, in spirit, another trade-selection idea (choose which optimization runs to trade) — see [[benfords-law]].
