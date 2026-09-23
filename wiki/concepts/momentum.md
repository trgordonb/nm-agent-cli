---
type: concept
title: "Momentum"
tags: [momentum, market-timing]
sources: [sector-rotation-trading-rules, historical-volatility-parameter-adjustment, trend-following-tail-risk-hedging-alpha, allocation-to-systematic-volatility-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Momentum

The tendency of recent relative performance to persist over intermediate horizons. Appears in this wiki in three roles:

- **Cross-sectional sector momentum:** ranking SPDR sector ETFs by 1–6 month returns; the optimal band flips with ranking length ([[sector-rotation]]), and top-rank avoidance trades CAR for MDD.
- **Time-series momentum as a timing signal:** 12-month vs 1-month lookbacks switched by volatility regime ([[market-timing]], [[historical-volatility-parameter-adjustment]]).
- **Trend-following vs stock momentum:** both exploit persistence, but trend-following produces *positive* convexity while market-neutral stock momentum produces *negative* convexity — trend-following carries stronger exposure to the autocorrelation factor ([[trend-following-tail-risk-hedging-alpha]], [[return-autocorrelation]]).

## Factor-model footnote

In Sepp's four-factor attribution of vol strategies, only the short-put strategy shows significant exposure to the momentum factor (UMD) — unsurprising given its net-long delta profile ([[allocation-to-systematic-volatility-strategies]]).
