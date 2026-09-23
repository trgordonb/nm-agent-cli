---
type: concept
title: "Volatility filtering (timing gates)"
tags: [volatility, market-timing]
sources: [historical-volatility-parameter-adjustment, spy-sso-tlt-strategy]
created: 2026-09-23
updated: 2026-09-23
---

# Volatility filtering (timing gates)

Using a volatility measure as a regime gate for a trading decision. Two distinct implementations in this wiki, with opposite verdicts:

1. **HV-conditional lookback switching** ([[historical-volatility-parameter-adjustment]]): 21-day HV < 17 → trust 12-month momentum; otherwise 1-month. Replication succeeded; every robust variant failed — the edge lived in the static constant, not the concept.
2. **VIX-level leverage gate** ([[spy-sso-tlt-strategy]]): VIX < 25 → hold SSO (2x) instead of SPY. The gate "made sense" and results were decent, but removing it (and SSO) cut MDD ~5 points for ~1 point of CAR — the *concept* was sound-ish, the *leverage* wasn't worth it.

## Contrast with statistical filtering

Sepp's [[statistical-filtering]] gates *option rolls* with a re-fit out-of-sample model and doubled Sharpe — the strongest filter result here. The difference is instructive: gate design (re-fit, prior-data-only, expected-value based) appears to matter more than the presence of a gate. And in [[regime-conditional-beta]] terms, all these gates are attempts to lower bear-regime exposure cheaply.
