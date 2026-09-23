---
type: source
title: "Volume and Mean Reversion"
authors: ["Cesar Alvarez"]
url: "https://alvarezquanttrading.com/blog/volume-and-mean-reversion/"
raw: "raw/volume-and-mean-reversion.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [mean-reversion, volume, trade-selection, research-methodology]
entities: [cesar-alvarez]
concepts: [mean-reversion, volume-filters, rsi, trade-selection]
---

# Volume and Mean Reversion (Alvarez, 2022)

Alvarez revisits whether volume carries predictive value for mean-reversion entries, having historically found volume either useless or too trade-restricting. Test: Russell 3000 stocks, 2007-01–2022-10, a simple mean-reversion setup — 2-period RSI < 1, close > $3, 21-day average dollar volume > $1M, entered next open, exited when 2-period RSI > 70 — evaluated as a trade list (not a portfolio), split by position relative to the 200-day MA. The new twist: use the *percent rank* of volume over the last 20 days (AmiBroker `PercentRank(V,20)`) rather than volume/average ratios, which he had tried before without success.

## Findings

- **Above the 200-day MA:** low-volume setups outperform — PercentRank 0–39 trades average +0.64% vs the +0.54% all-trade average (+18%), but those buckets contain only ~18% of trades (33% of trades occur in the highest-volume bucket of the last 20 days).
- **Below the 200-day MA:** the low-volume edge is even stronger in relative terms, though overall trade quality is much worse below the MA (avg +0.15%) — interestingly the *reverse* of the author's own production strategy's behavior.
- **Portfolio integration:** adding `PercentRank(Volume,20) < 20` as a filter to his live strategy cuts exposure from 25% to 5% but lifts average %P/L from 1.87% to 2.58% with slightly more winners. *Ranking* low-volume signals higher instead of filtering preserves trade count and yields small improvements in CAR, Ulcer Index, avg %P/L, % winners, and Sharpe.

## Author's decision

He will **not** add the filter: the improvement is small and does not justify added complexity — he wants a larger improvement before adding rules. He notes the finding is useful for discretionary quant traders, who can prioritize trades and size positions when low-volume setups appear. Directionally surprising result: *low* volume, not high, enhances the mean-reversion edge.

## Where this fits

- [[cesar-alvarez]] — author.
- [[mean-reversion]] — the strategy family; RSI(2) machinery.
- [[volume-filters]] — percent-rank volume as signal modifier.
- [[rsi]] — the 2-period RSI entry/exit engine.
- [[trade-selection]] — filter-vs-rank tradeoff for signal prioritization.
