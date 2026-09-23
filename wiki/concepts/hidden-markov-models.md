---
type: concept
title: "Hidden Markov models (in volatility forecasting)"
tags: [volatility, machine-learning, forecasting]
sources: [machine-learning-for-volatility-trading]
created: 2026-09-23
updated: 2026-09-23
---

# Hidden Markov models (in volatility forecasting)

State-space models in which an unobserved market state (e.g., trending vs range-bound, calm vs stressed) evolves as a Markov chain and generates observable price behavior. In Sepp's four-class comparison of ~40 volatility models, HMC models were **one of the best forecasters across many asset classes** ([[machine-learning-for-volatility-trading]]).

## The cyclical caveat

HMC dominance is regime-dependent: best in strong trends, overtaken by simple [[volatility-estimators]] in range-bound markets. Their edge is precisely that they model regime — which pays off when regimes persist and costs when they churn. This makes HMC the natural engine for [[model-cycling]] and connects directly to [[regime-conditional-beta]]: both treat the unobserved state as the first-class object.

## Open questions

- Single-source claim (presentation summary); the SSRN paper's out-of-sample tests are the needed corroboration.
