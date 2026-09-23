---
type: concept
title: "Model cycling"
tags: [machine-learning, forecasting, regime-analysis]
sources: [machine-learning-for-volatility-trading, allocation-to-systematic-volatility-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Model cycling

The observation that no single forecasting model stays best: model rankings rotate with market regime, so the selection layer must itself adapt. Sepp's evidence: hidden-Markov models lead in strong trends, simple [[volatility-estimators]] lead in range-bound markets, and a reinforcement-learning aggregation dynamically re-selects the best of ~40 models out-of-sample ([[machine-learning-for-volatility-trading]]).

## The same pattern in trading rules

The structure recurs outside ML: in Alvarez's sector-rotation test, the optimal *rank window* flips with the evaluation horizon (ranks 4–6 best at 1-month ranking, ranks 1–3 best at 3-month, convergence at 6-month — [[sector-rotation-trading-rules]]); and Sepp's own filter thresholds are re-fit strictly out-of-sample at each roll ([[statistical-filtering]]). Fixed parameters ride cycles; adaptive selection is the common response.

## Dangers

- The selection layer is itself a parameter: switching logic can be overfit (see [[overfitting]], [[parameter-robustness]]).
- Cycle detection lags regime turns — the cost side of adaptation.
