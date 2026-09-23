---
type: concept
title: "Backtesting (practice and pitfalls)"
tags: [backtest, research-methodology]
sources: [benford-law-strategy-selection, historical-volatility-parameter-adjustment, sector-rotation-trading-rules, spy-sso-tlt-strategy, volume-and-mean-reversion, machine-learning-for-volatility-trading, crypto-smart-beta-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Backtesting (practice and pitfalls)

All ten ingested sources are backtest-driven; their collective methodological practice is itself a finding.

## Documented practices

- **Replicate first, then perturb:** Alvarez never trusts a published result until reproduced on his own data (AmiBroker + Norgate), then stress-tests one assumption at a time ([[historical-volatility-parameter-adjustment]], [[sector-rotation-trading-rules]], [[spy-sso-tlt-strategy]]).
- **In-sample/out-of-sample splits:** tercile persistence tests for optimization runs ([[benford-law-strategy-selection]]); Sepp's filters and ML selection use strictly prior data at every decision ([[statistical-filtering]], [[look-ahead-bias]]).
- **Recent-window re-testing:** published backtests from 1954/2001 are re-run from 2000/2010 — regimes change, and post-2010 bull markets flatter everything vs buy-and-hold ([[regime-analysis]] via [[regime-conditional-beta]]).
- **Rule removal as a test:** the SSO study's meta-lesson — deleting the leverage rule improved risk-adjusted results ([[spy-sso-tlt-strategy]]).
- **Simulation for short samples:** bootstrapped joint paths when history is too thin ([[bootstrapping-simulation]]).

## Pitfalls catalogued

[[overfitting]] (the master), [[look-ahead-bias]] (calibration leakage), hidden tail risk from unconditional aggregation ([[regime-conditional-beta]]), model-selection bias amplified by vol targeting ([[volatility-targeting]]), and marketing-driven backtests ([[trend-following-ctas-vs-arp-products]]: "nice looking back-tested results obtained by over-fitted models").

## Reporting norms observed

Both authors report CAR alongside MDD/Sharpe/Ulcer and treat MDD parity as decisive — return improvement without drawdown improvement is not an improvement.
