---
type: concept
title: "Volatility carry strategies"
tags: [volatility, risk-premia]
sources: [allocation-to-systematic-volatility-strategies, trend-following-ctas-vs-arp-products]
created: 2026-09-23
updated: 2026-09-23
---

# Volatility carry strategies

Systematic strategies that sell volatility to capture the [[volatility-risk-premia]]. Sepp's canonical trio (S&P 500 based):

| Strategy | Position | Profit source | Tail behavior |
| --- | --- | --- | --- |
| Put | Short 1-month ATM SPX puts monthly | Premium + ~50% net delta | Loses with SPX; hedged variants keep tail correlation |
| Strangle | Short 20-delta put + call | Skew + convexity premia; delta-neutral at inception | Disproportionately tail-sensitive |
| VIX futures | Short 1st/2nd-month VIX futures | Contango roll yield (~90% annualized) | High SPX beta in tails (cf. XIV, Feb 2018) |

## Design dimensions

Raw carry has poor skewness and deep drawdowns relative to volatility, so implementation quality dominates: a [[statistical-filtering]] roll filter roughly doubled Sharpe in backtest, and [[delta-hedging]] removed market beta almost entirely ([[allocation-to-systematic-volatility-strategies]]). [[volatility-targeting]] aligns the three variants' risk for comparison and allocation.

## Regime view

Under [[regime-conditional-beta]] analysis these are all **risk-seeking** strategies: positive risk-premia alpha bought with positive marginal bear betas ([[trend-following-ctas-vs-arp-products]]). "Market-neutral" presentations of them aggregate away the crisis regime.
