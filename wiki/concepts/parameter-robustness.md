---
type: concept
title: "Parameter robustness"
tags: [research-methodology, backtest, overfitting]
sources: [historical-volatility-parameter-adjustment, sector-rotation-trading-rules, spy-sso-tlt-strategy, volume-and-mean-reversion]
created: 2026-09-23
updated: 2026-09-23
---

# Parameter robustness

The requirement that a strategy's edge survive perturbation of its parameters. Alvarez's corpus is effectively a sequence of robustness audits, and the failures are the findings:

- **HV threshold 17:** best-CAR *and* best-MDD at exactly 17 — the overfit signature. The 80th-percentile value recomputed from 1999 forward is 21.2; results hold only for cutoffs 15–25 and collapse entirely under point-in-time calibration ([[historical-volatility-parameter-adjustment]]).
- **Sector rank window:** "buy ranks 4,5,6" wins at 1-month ranking, loses to ranks 1–3 at 3-month, converges at 6-month. The rule was a ranking-length artifact, not a structural edge ([[sector-rotation-trading-rules]]).
- **VIX<25:** one point on a smooth CAR/MDD frontier; lower cutoffs buy CAR with MDD, higher ones buy MDD with CAR. No magic value — which itself argues the parameter is doing something real but not *tuned* ([[spy-sso-tlt-strategy]]).
- **Volume filter:** a *real* but small edge — improvement did not justify added complexity, showing robustness is necessary but not sufficient for adoption ([[volume-and-mean-reversion]]).

## The asymmetry that matters

Dynamic/adaptive variants of parameters usually behave like static ones; when they *don't* — as with the HV threshold, where every look-ahead-free variant failed on MDD — that divergence is itself the alarm ([[look-ahead-bias]], [[volatility-filtering]]).

Contrast: Sepp's [[statistical-filtering]] result shows a filter *can* be robustly powerful when the model is re-fit strictly out-of-sample at every decision point — the discipline, not the constant, carries the edge.
