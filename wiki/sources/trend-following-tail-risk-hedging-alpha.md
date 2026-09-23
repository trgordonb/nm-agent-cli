---
type: source
title: "Trend-following strategies for tail-risk hedging and alpha generation"
authors: ["Artur Sepp"]
url: "https://artursepp.com/2018/04/24/trend-following-strategies-for-tail-risk-hedging-and-alpha-generation/"
raw: "raw/trend-following-tail-risk-hedging-alpha.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [trend-following, cta, tail-risk, convexity, momentum]
entities: [artur-sepp]
concepts: [trend-following, crisis-alpha, convexity, tail-risk-hedging, return-autocorrelation, volatility-targeting]
---

# Trend-following strategies for tail-risk hedging and alpha generation (Sepp, 2018)

Companion post to Sepp's SSRN paper 3167787. Thesis: trend-following's adaptive position sizing generates positive return skewness (infrequent large gains vs frequent small losses) and positive convexity to equity indices (large gains in both very bearish and very bullish markets), making trend-followers viable diversifiers and alpha generators — but only when evaluated at the right measurement frequency and trend speed.

## Key claims

- **Hedge fund landscape (Eurekahedge indices):** long-vol funds have positive skew but not positive convexity; tail-risk funds have skew and convexity but strongly negative overall performance; short-vol funds have significant negative convexity in tails; trend-following CTAs uniquely combine significant positive convexity with positive overall performance.
- **Measurement frequency:** trend-followers show positive skew and convexity at monthly, quarterly, and annual measurement; Sepp recommends *quarterly* returns for evaluation. Convexity appears only when the return measurement period exceeds the half-life of the trend smoothing plus the rebalancing period.
- **Tail hedging:** conditional on S&P 500 quarterly-return quantiles, trend-followers generate significant positive returns with positive skew in the worst index quintiles; negative returns with positive skew in range-bound middles; large positive returns in strong up markets.
- **Autocorrelation driver:** trend-followers profit from autocorrelated prices. The 2011–2018 underperformance of trend-followers coincides with significantly negative lag-1 autocorrelation of monthly/quarterly S&P 500 returns (a mean-reverting regime despite positive drift). Sepp introduces an alternative autocorrelation measure with strong explanatory power for SG trend index returns.
- **Speed matters:** fast smoothing (half-life < ~1 quarter) → better protection in sharp short-lived reversals but suffers in choppy markets; medium/slow smoothing (half-life ¼–1 year) → better as long-horizon alpha. Fast-paced CTAs notably outperformed in the February 2018 volatility reversal. Slow smoothing = higher beta to the underlying.
- **Trend vs stock momentum:** trend-following has stronger exposure to the autocorrelation factor and produces *positive* convexity, while market-neutral stock momentum produces *negative* convexity.
- **Allocation:** a 50/50 mix of SG trend CTA index and HFR risk-parity fund index halves the drawdown versus pure risk parity at the same Sharpe, because the two strategies' drawdown occurrences are independent.

## Method notes

Trend system parameterized by trend-smoothing half-life and rebalance frequency; a 4-month half-life replication correlates significantly with BTOP50 and SG trend indices from the 2000s.

## Open questions

- Single-author replication of the SG/BTOP50 indices; the autocorrelation-explanatory-power claim rests on Sepp's own alternative measure.
- Sample ends 2018; the regime-dependence claims invite later-data corroboration.

## Where this fits

- [[artur-sepp]] — author.
- [[trend-following]] — the central subject; see also [[trend-following-ctas-vs-arp-products]].
- [[crisis-alpha]] — the tail-hedging / negative bear-beta evidence.
- [[convexity]] — skewness and convexity as the risk-profile metrics.
- [[tail-risk-hedging]] — allocation use-case.
- [[return-autocorrelation]] — the explanatory regime factor.
- [[volatility-targeting]] — referenced Lo-style vol-targeting context.
