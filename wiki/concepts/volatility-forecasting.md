---
type: concept
title: "Volatility forecasting"
tags: [volatility, forecasting]
sources: [machine-learning-for-volatility-trading, historical-volatility-parameter-adjustment]
created: 2026-09-23
updated: 2026-09-23
---

# Volatility forecasting

Predicting future realized volatility, which is unobservable even retrospectively at the same granularity as returns and must be inferred from price/tick data. Sepp estimates 200–300 competing model families exist (intraday estimators, GARCH-type, continuous-time, Bayesian, hidden-Markov), making selection the central problem rather than model invention ([[machine-learning-for-volatility-trading]]).

## Findings in this wiki

- Across ~40 implemented models, **Hidden Markov Chain models** ([[hidden-markov-models]]) are among the best forecasters across asset classes — but rankings are cyclical: HMC leads in trending markets, simple [[volatility-estimators]] lead in range-bound ones. Dynamic model selection (see [[model-cycling]]) is the proposed answer.
- Forecast choice is not academic: inside a [[volatility-targeting]] strategy, model choice can swing results by orders of magnitude (Lo's 40x example) — [[overfitting]] enters through the forecast, not just the trading rule.
- On the simpler end, Alvarez's timing tests use raw 21-day historical volatility as a regime switch ([[volatility-filtering]]) — and show how fragile a *threshold on* a volatility measure can be ([[historical-volatility-parameter-adjustment]]).

## Open questions

- The ML selection results are presentation-level summaries; the SSRN paper (3186401) holds the model lists and test construction. Hedge until corroborated.
