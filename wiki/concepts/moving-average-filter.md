---
type: concept
title: "Moving average filter"
tags: [market-timing, technical]
sources: [spy-sso-tlt-strategy, volume-and-mean-reversion]
created: 2026-09-23
updated: 2026-09-23
---

# Moving average filter

Trend gate comparing price to a trailing moving average (typically the 200-day) to classify regime. In this wiki:

- Applied to SPY as the stock/bond selector in the SSO rotation strategy ([[spy-sso-tlt-strategy]]).
- Applied recursively to *both* legs — SPY below its MA *and* TLT below its own MA → cash — which "has a huge impact on MDD with only a slight change in CAR" by exiting the failed bond hedge in 2022-style environments.
- Used as a conditioning variable rather than a signal in [[volume-and-mean-reversion]]: mean-reversion trade quality is split above/below the 200-day MA, where low-volume setups behave differently on each side.

## Observations

The filter is coarse but sturdy — none of the sources found the 200-day MA itself fragile; the fragile parts were the layered parameters around it ([[parameter-robustness]]). Its 2022 lesson, though: an MA filter on the *hedge leg* was missing from strategies that assumed bonds always hedge stocks.
