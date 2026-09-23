---
type: concept
title: "Delta hedging"
tags: [volatility, hedging]
sources: [allocation-to-systematic-volatility-strategies, trend-following-ctas-vs-arp-products]
created: 2026-09-23
updated: 2026-09-23
---

# Delta hedging

Continuously offsetting the directional (delta) exposure of an option position, converting it into a pure position in implied-vs-realized volatility. In Sepp's 2017 backtest, adding delta-hedging to filtered put and strangle strategies made market-factor exposure statistically insignificant, cut average pairwise strategy correlation to ~0.25, and produced the strongest risk-adjusted results of all variants ([[allocation-to-systematic-volatility-strategies]]).

## What delta hedging does not fix

A delta-hedged short put still carries negative gamma and vega. Under regime-conditional analysis its market beta is small in normal regimes but significant in crises — the canonical example of hidden tail exposure used in [[trend-following-ctas-vs-arp-products]] to dismantle "market-neutral" claims. Delta hedging neutralizes first-order risk; it concentrates, rather than removes, tail risk.

## Where this fits

Central mechanism of [[volatility-carry-strategies]]; distinct from [[statistical-filtering]] (which gates entries) and from defensive tail protection ([[tail-risk-hedging]]).
