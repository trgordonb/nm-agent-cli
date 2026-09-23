---
type: concept
title: "Statistical filtering (roll filter)"
tags: [volatility, hedging]
sources: [allocation-to-systematic-volatility-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Statistical filtering (roll filter)

Sepp's entry gate for volatility carry rolls: at each rebalancing date, fit a time-series model on data *strictly prior* to the date, compute the expected value of the upcoming roll, and skip the roll if the expectation falls below a threshold. No in-life hedging is applied by the filter itself; it is combined with [[delta-hedging]] in the "Filter+Hedge" variants.

## Backtest effect

On the same 2005–2017 sample and 10% [[volatility-targeting]], the filter roughly **doubled Sharpe and halved drawdowns** versus vanilla carry, cut SPX beta from ~0.5 to ~0.2, and moved alpha from insignificant to significant ([[allocation-to-systematic-volatility-strategies]]). This makes it one of the strongest documented "process beats raw exposure" results in this wiki.

## Caveats

- The post does not specify the time-series model or the threshold — the edge cannot be reproduced from the source alone.
- Related but distinct: [[volatility-filtering]] (Alvarez's HV/VIX regime gates for timing equity exposure) gates a *different* decision (position vs no position in an index) and showed much more fragile results.
