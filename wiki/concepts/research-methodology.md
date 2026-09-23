---
type: concept
title: "Research methodology (quant trading)"
tags: [research-methodology]
sources: [benford-law-strategy-selection, historical-volatility-parameter-adjustment, sector-rotation-trading-rules, spy-sso-tlt-strategy, volume-and-mean-reversion, machine-learning-for-volatility-trading, trend-following-ctas-vs-arp-products]
created: 2026-09-23
updated: 2026-09-23
---

# Research methodology (quant trading)

The working epistemology shared (differently) by the two authors in this wiki.

## Alvarez's rules, extracted from practice

1. Replicate before believing; perturb after replicating ([[parameter-robustness]]).
2. Recent windows over glorious histories — 2000+ or 2010+ — because regimes move ([[regime-analysis]]).
3. Test rule *removal*, not just addition ([[spy-sso-tlt-strategy]]).
4. Demand a bigger improvement before adding complexity ([[volume-and-mean-reversion]]).
5. Validate an idea on a second strategy before trusting the first result ([[benford-law-strategy-selection]]).
6. Publish negative results; they are the evidence the process works ([[benford-law-strategy-selection]]).
7. Camp 1: hold only strategies whose trades you can explain to yourself during a drawdown; opacity is disqualifying regardless of stats ([[sector-rotation-trading-rules]]).

## Sepp's rules, extracted from practice

1. Disaggregate by regime before judging anything ([[regime-conditional-beta]]).
2. Re-fit models strictly on prior data at every decision point ([[statistical-filtering]], [[look-ahead-bias]]).
3. When model counts explode, add a selection layer disciplined by out-of-sample tests and MDL ([[machine-learning-for-volatility-trading]], [[minimum-description-length]]).
4. Match evaluation frequency to strategy adaptation speed (quarterly for trend-following) ([[trend-following-tail-risk-hedging-alpha]]).
5. Treat marketing claims of market-neutrality as aggregation artifacts until regime-tested ([[trend-following-ctas-vs-arp-products]]).

## The convergence

Opposite tolerance for complexity, identical bottom line: **the backtest is the beginning of the argument, not the end** — the unifying stance of [[overfitting]].
