---
type: source
title: "Allocation to systematic volatility strategies using VIX futures, S&P 500 index puts, and delta-hedged long-short strategies"
authors: ["Artur Sepp"]
url: "https://artursepp.com/2017/09/20/allocation-to-systematic-volatility-strategies-using-vix-futures-sp-500-index-puts-and-delta-hedged-long-short-strategies/"
raw: "raw/allocation-to-systematic-volatility-strategies.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [volatility, risk-premia, backtest, portfolio-allocation]
entities: [artur-sepp]
concepts: [volatility-risk-premia, volatility-carry-strategies, delta-hedging, statistical-filtering, volatility-targeting, crisis-alpha]
---

# Allocation to systematic volatility strategies (Sepp, 2017)

Sepp presents three systematic volatility carry strategies — short S&P 500 ATM puts, short 20-delta strangles, and short VIX futures — each run in three hedging variants (vanilla, +statistical filter, +filter with delta-hedging or long/short), volatility-targeted to 10% annual vol, back-tested January 2005–September 2017. Core findings: the statistical filter roughly doubles Sharpe and halves drawdowns; adding delta-hedging reduces market beta to insignificance and cuts pairwise strategy correlation to ~0.25; allocating 10% of a benchmark portfolio to these strategies boosts alpha by ~1% and Sharpe by 10–20%.

## Strategy definitions

| Strategy | Implementation | Source of profit | Principal risk |
| --- | --- | --- | --- |
| Put | Sell 1-month ATM SPX puts monthly (like CBOE PUT) | Put premium + ~50% delta to SPX | Significant delta exposure |
| Strangle | Sell 1-month 20-delta put + call (like CBOE CNDR) | Skew and convexity premiums; near delta-neutral | Disproportionately tail-sensitive |
| VIX | Sell 1st/2nd-month VIX futures (like XIV) | Contango roll yield (~90% annualized) | Contango/backwardation regime dependence; high SPX beta in tails |

## Hedging variants

1. **Vanilla** — systematic rolls, no hedge.
2. **Filter** — a time-series model fitted on data strictly prior to each roll date computes the expected value of the roll; if below a threshold, the roll is skipped. No in-life hedging.
3. **Filter+Hedge** (options strategies) — filter plus delta-hedging to expiry.
4. **Filter+Long/Short** (VIX strategy) — short in contango, long in backwardation, sized by signal strength.

## Backtest results (2005–Sep 2017)

Benchmarks: SPY, TLT (20y Treasuries), and a monthly-rebalanced 50/50 SPY/TLT portfolio. Per the source's analysis:

- Vanilla: Sharpe comparable to SPY with smaller drawdowns, beta ~0.5, insignificant alpha, average pairwise correlation ~0.7.
- Filtered: Sharpe ~2x vanilla, drawdowns ~halved, beta ~0.2, statistically significant alpha, pairwise correlation ~0.5.
- Filter+Hedge: strongest risk-adjusted results, very small beta, significant alpha, pairwise correlation ~0.25; the long/short VIX variant produced *negative* correlation/beta to all three benchmarks.

A four-factor Fama-French-Carhart attribution (AQR data) shows insignificant loadings on SMB/HML/UMD for all strategies (put has significant momentum exposure); market-factor exposure shrinks with the filter and becomes insignificant with delta-hedging.

## Portfolio-level conclusions

With 10% of funds allocated and monthly rebalancing: vanilla strategies add little to SPY- or 50/50-benchmarked portfolios (but help bond-benchmarked ones via their equity overlay); filtered strategies add significantly to all benchmarks; the delta-hedged strangle and long/short VIX strategies improve all three benchmarks most consistently, while the delta-hedged put retains tail correlation to SPY that limits its marginal contribution.

## Open questions

- Results end September 2017; the short-VIX variant's tail behavior (XIV's February 2018 collapse) is outside the sample — see [[trend-following-ctas-vs-arp-products]] for the regime-conditional critique of such hidden tail exposure.
- Filter threshold values and the specific time-series model are not given in the post.

## Where this fits

- [[artur-sepp]] — author.
- [[volatility-risk-premia]] — the premium being harvested.
- [[volatility-carry-strategies]] — the three strategy archetypes.
- [[delta-hedging]] — the hedge that removes market beta.
- [[statistical-filtering]] — the roll filter design.
- [[volatility-targeting]] — 10% vol targeting methodology.
- [[crisis-alpha]] — negative-correlation tail behavior of the L/S VIX variant; contrast with [[trend-following-tail-risk-hedging-alpha]].
