---
type: concept
title: "Volatility estimators"
tags: [volatility, forecasting]
sources: [machine-learning-for-volatility-trading]
created: 2026-09-23
updated: 2026-09-23
---

# Volatility estimators

The measurement layer of [[volatility-forecasting]]: estimators that infer latent volatility from price data. Sepp's model zoo includes intraday estimators as one of four classes (with GARCH-type, Bayesian, and hidden-Markov models), totaling ~40 implementations ([[machine-learning-for-volatility-trading]]).

## Finding

Simple intraday estimators outperform sophisticated models **in range-bound markets**, while hidden-Markov models win in trending ones — the cyclical-ranking result behind [[model-cycling]]. The practical implication is that no single estimator dominates; regime-aware selection does.

## Open questions

- The post does not enumerate which intraday estimators (e.g., realized variance variants) were used; details live in the SSRN paper.
