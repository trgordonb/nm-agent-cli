---
type: source
title: "Sector Rotation Strategy: Should Trading Rules Make Sense?"
authors: ["Cesar Alvarez"]
url: "https://alvarezquanttrading.com/blog/sector-rotation-strategy-should-trading-rules-make-sense/"
raw: "raw/sector-rotation-trading-rules.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [sector-rotation, momentum, parameter-robustness, regime-analysis]
entities: [cesar-alvarez]
concepts: [sector-rotation, momentum, parameter-robustness, regime-sensitivity, market-timing]
---

# Sector Rotation Strategy: Should Trading Rules Make Sense? (Alvarez, 2023)

Alvarez replicates a published sector-rotation strategy with an odd twist: instead of buying the top three SPDR sector ETFs by 1-month return (XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY), it buys ranks 4, 5, 6 — justified only by "it works." He uses it to probe the two camps on trading rules: rules must make sense vs. stats-are-enough-if-overfit-tests-pass.

## Test

- Monthly, last trading day: rank the nine sector ETFs by 1-month return, buy ranks 4–6 equal-weighted at next open, sell all prior month's holdings. Tested 2010-01–2023-09 (the original used 2001 onward).
- Variations: ranking lengths 1/2/3/4/6 months, 2–4 positions, different rank starts.

## Results

- With 1-month ranking, buying 4,5,6 gives the best CAR; buying 1,2,3 is clearly the *worst* by CAR and Sharpe; buying 2,3,4 matches 4,5,6 with better MDD and Sharpe.
- With 3-month ranking, 1,2,3 becomes best but the spread narrows; with 6-month ranking, results converge further. The "middle-three" edge is therefore an artifact of the short ranking window, not a stable rule.
- Buy-and-hold SPY over the same period has only slightly lower CAR/Sharpe with none of the work — a recurring pattern in post-2010 markets.

## Author's position

Alvarez is "mostly camp 1": he needn't know why every rule exists, but needs a high-level causal understanding plus evidence the strategy isn't parameter-sensitive and survives out-of-sample testing. His car analogy: know how the car works at a high level, not the internals. The decisive argument: *sticking with a strategy is easy while it makes money; when it loses, the trader needs to understand why the trades are happening* to hold on. He distinguishes this from black boxes generally — he would trade a signal service with a comprehensible high-level concept from a trusted creator, but not opaque, parameter-sensitive ML-driven systems.

## Where this fits

- [[cesar-alvarez]] — author.
- [[sector-rotation]] — the strategy genre under test.
- [[momentum]] — cross-sectional momentum on sectors; the rank-1-avoidance variant.
- [[parameter-robustness]] — the ranking-length sensitivity that dissolved the rule.
- [[regime-analysis]] — the 2010s bull market flattering rotation strategies vs buy-and-hold.
- [[market-timing]] — monthly-rebalanced ETF timing family (cf. [[spy-sso-tlt-strategy]]).
