---
type: concept
title: "Stock-bond correlation (regime risk)"
tags: [portfolio-allocation, market-timing, regime-analysis]
sources: [spy-sso-tlt-strategy, allocation-to-systematic-volatility-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Stock-bond correlation (regime risk)

The assumption that Treasuries hedge equity drawdowns is regime-dependent, and 2022 broke it: stocks and bonds fell together, so any strategy that treats TLT as the default bear-market asset inherits correlated tail risk. Alvarez: "Many people created strategies assuming if SPY was in a bear market, that TLT would be a good alternative. Myself included. 2022 fixed that illusion" ([[spy-sso-tlt-strategy]]).

## Practical responses documented

- **Double MA gate:** hold TLT only when TLT is also above its own 200-day MA; otherwise cash. Large MDD improvement, slight CAR change.
- **Bond-benchmark overlays:** Sepp's vol strategies helped bond-benchmarked portfolios because their equity overlay offsets rates risk in bull conditions — the same correlation working in reverse ([[allocation-to-systematic-volatility-strategies]]).

## Status

Single-event evidence (2022) in this wiki; the correlation regime as a *forecastable* variable is an open question connecting to [[regime-analysis]] thinking throughout.
