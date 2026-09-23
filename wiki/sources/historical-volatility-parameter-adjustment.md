---
type: source
title: "Using Historical Volatility for Parameter Adjustment"
authors: ["Cesar Alvarez"]
url: "https://alvarezquanttrading.com/blog/using-historical-volatility-for-parameter-adjustment/"
raw: "raw/historical-volatility-parameter-adjustment.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [market-timing, volatility, parameter-robustness, negative-result]
entities: [cesar-alvarez]
concepts: [volatility-filtering, parameter-robustness, look-ahead-bias, market-timing]
---

# Using Historical Volatility for Parameter Adjustment (Alvarez, 2022)

A replication-and-robustness study of the "Trending Fast and Slow" SPX timing idea (via AllocateSmartly): condition the momentum lookback on historical volatility — in a low-HV regime use a 12-month return signal, otherwise a 1-month signal, switching on a 21-day HV threshold of 17 (its ~80th percentile since 1954). Monthly entries/exits at the last trading day's close.

## Replication

Alvarez's 1954-forward replication matches the original (similar CAR to buy-and-hold, MDD less than half) and performs well from 2000–2022.

## Robustness tests — where it breaks down

1. **Static threshold sensitivity:** using data from 1999 forward, the 80th-percentile 21-day HV is 21.2, not 17 — a materially different parameter. Optimization over cutoffs 10–30 shows similar results only within 15–25, and 17 happens to be both best-CAR and best-MDD, an overfit signature.
2. **Point-in-time (dynamic) threshold:** computing the 80th percentile only from data available at each trade date — eliminating look-ahead — produces results near buy-and-hold (horrible at the 80th percentile; MDD near buy-and-hold even at 85–90).
3. **Rolling windows:** 10-year rolling lookback with percent-rank ≥85 thresholds works on CAR across lookbacks but MDD is near buy-and-hold in all cases.

## Conclusion and author's decision

The static-threshold version's success depends on the full-history-calibrated constant 17; every look-ahead-free variant degrades sharply on drawdown (dynamic variants CAR >6% but MDD >40% vs <28% static). Alvarez declines to add the concept to his dual-momentum strategies — inconsistency of results under parameter perturbation is disqualifying, even though he liked the concept. Notable meta-point: normally dynamic and static threshold variants produce similar results; here they did not, which is itself the warning.

## Where this fits

- [[cesar-alvarez]] — author.
- [[volatility-filtering]] — HV as a regime switch for signal selection.
- [[parameter-robustness]] — the central lesson: the edge lived in a fragile constant.
- [[look-ahead-bias]] — the dynamic-threshold experiment isolates it.
- [[market-timing]] — the strategy genre.
