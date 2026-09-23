---
type: source
title: "Benford's Law and Strategy Selection"
authors: ["Cesar Alvarez"]
url: "https://alvarezquanttrading.com/blog/benfords-law-and-strategy-selection/"
raw: "raw/benford-law-strategy-selection.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [research-methodology, overfitting, negative-result]
entities: [cesar-alvarez]
concepts: [benfords-law, overfitting, backtest]
---

# Benford's Law and Strategy Selection (Alvarez, 2022)

A documented negative result: Alvarez tests whether Benford's Law compliance of a strategy's daily return stream can identify non-curve-fit strategies from an optimization run. Hypothesis: failure to follow Benford's Law implies curve-fitting, so in-sample top-CAR runs whose Chi-Square statistic is lowest should persist in the out-of-sample top CAR tercile.

## Setup

- Benford's Law prerequisites: several orders of magnitude in the data, an unbounded min or max, thousands of observations, data not concentrated around the mean. Daily stock percentage returns violate the last condition.
- Baselines: SPY daily returns 2007–2021 give Chi-Square 17.9 (vs the conventional 15.5 cutoff for Benford compliance); S&P 500 constituent stocks 2007–2021 average 44.4 (range 5–102; only 7 of ~500 stocks under 15.5). Alvarez concludes the data are simply a poor fit for the law rather than evidence of manipulation.
- Strategy tests: a momentum strategy (432 optimization runs, 2007–2016) and a mean-reversion strategy; top-CAR tercile split into Chi-Square terciles; out-of-sample CAR terciles computed.

## Results

- Momentum: a clear diagonal pattern emerged — but in the *opposite* direction of the hypothesis (highest Chi-Square tercile, not lowest, persisted in out-of-sample top CAR).
- Mean reversion: no pattern at all; random.
- Alvarez's own strategy-optimization Chi-Square values (210–2143) are far outside any Benford-compliant range.

## Takeaways recorded by the author

- Test an idea on a second strategy before believing the first result — the momentum diagonal was a mirage that a second test dissolved.
- An idea can "work" statistically yet be untradable if no causal story makes the trader comfortable.
- Careful, pre-publication error-catching matters (the author credits a proofreader for catching a major logical mistake).

## Where this fits

- [[cesar-alvarez]] — author.
- [[benfords-law]] — the tested instrument and its data prerequisites.
- [[overfitting]] — the curve-fitting detection motivation.
- [[backtest]] — in-sample/out-of-sample tercile methodology.
