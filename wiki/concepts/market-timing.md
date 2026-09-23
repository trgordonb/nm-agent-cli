---
type: concept
title: "Market timing (monthly ETF strategies)"
tags: [market-timing, etf-rotation]
sources: [spy-sso-tlt-strategy, historical-volatility-parameter-adjustment, sector-rotation-trading-rules]
created: 2026-09-23
updated: 2026-09-23
---

# Market timing (monthly ETF strategies)

Month-end decision rules that rotate among broad ETFs based on trend and volatility conditions. Three ingested studies fall here, sharing machinery and pitfalls:

- **SPY/SSO/TLL rotation** ([[spy-sso-tlt-strategy]]): 200-day [[moving-average-filter]] on SPY picks stocks vs TLT; a VIX level ([[volatility-filtering]]) picks leveraged SSO vs SPY. Iteration taught: add a TLT filter for the 2022-style joint bear market ([[stock-bond-correlation]]), then discover removing SSO entirely cuts MDD ~5 for ~1 CAR — leverage added volatility, not return.
- **HV-conditioned SPX timing** ([[historical-volatility-parameter-adjustment]]): switch 12-month vs 1-month momentum lookback on a 21-day HV threshold. Replicated fine; every look-ahead-free calibration of the threshold collapsed toward buy-and-hold.
- **Sector rotation** ([[sector-rotation-trading-rules]]): monthly cross-sectional [[momentum]] on nine SPDR sector ETFs. Optimal rank band flips with ranking length; post-2010 the whole genre barely beats buy-and-hold.

## Recurring findings

1. Drawdown control, not CAR, is where timing earns its keep (every study's MDD improvement outpaces its return improvement).
2. Parameters look reasonable but are rarely robust ([[parameter-robustness]]).
3. Buy-and-hold since 2010 is a stronger baseline than most published variants — "the markets of the last 13 years have been hard to beat."
