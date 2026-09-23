---
type: source
title: "Trend-Following CTAs vs Alternative Risk-Premia (ARP) products: crisis beta vs risk-premia alpha"
authors: ["Artur Sepp"]
url: "https://artursepp.com/2019/02/05/trend-following-ctas-vs-alternative-risk-premia-arp-products-crisis-beta-vs-risk-premia-alpha/"
raw: "raw/trend-following-ctas-vs-arp-products.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [trend-following, cta, risk-premia, tail-risk, regime-analysis]
entities: [artur-sepp]
concepts: [risk-premia-alpha, regime-conditional-beta, crisis-alpha, trend-following, tail-risk-hedging, overfitting]
---

# Trend-Following CTAs vs ARP products (Sepp, 2019)

Post expanding a Hedge Fund Journal article co-authored by Sepp. It introduces a regime-conditional CAPM model for classifying systematic strategies by their marginal bear-market beta, applied to ~200 composite indices (73 hedge fund indices, 7 CTA indices, 38 HFR Bank Systematic Risk-premia indices). Context: 2018, when ARP products sold as market-neutral failed badly (HFR Bank Systematic Risk-premia Multi-Asset Index −18% vs −4% for the S&P 500 TR; SG Trend Index −8%; HFRX Global HF −7%).

## The model and its findings

- **Risk-seeking strategies:** positive marginal bear beta (risk *increases* in bear regimes), compensated by positive risk-premia alpha. Most hedge fund and ARP products sit here; there is an almost linear cross-sectional relationship between risk-premia alpha and marginal bear beta. ARP products deliver *less* alpha per unit of tail risk than hedge funds.
- **Defensive strategies:** negative marginal bear beta, compensated by negative risk-premia alpha (you pay for crisis protection). Long-vol style.
- **Trend-following CTAs (the anomaly):** negative marginal bear betas — they diversify equity risk in bear regimes — yet their risk-premia alpha is statistically insignificant. CTAs are neither tail-risk sellers (ARPs) nor paid insurance (defensive long-vol); they are actively managed defensive strategies delivering protective negative betas in down markets and risk-seeking positive betas in strong up markets.
- The model explains ~90% of risk-premia for volatility strategies and ~35% for hedge fund/ARP products generally.

## Interpretive claims

- "Zero-correlated" / "market-neutral" marketing is a regime-aggregation artifact: e.g., a delta-hedged short-put strategy has small beta in normal regimes but significant crisis beta through negative gamma/vega exposure. Unconditional performance aggregates away the regime-conditional risk.
- 2018 underperformance had different causes: ARP products failed because their excess returns are compensation for hidden tail risk that materialized; trend-followers failed (milder) because trends reversed rapidly multiple times — trend-following returns are conditional on trends persisting for sustained periods (at least ~2 months to adjust).
- Implication: evaluate ARP-type products only over horizons containing both bull and bear regimes.

## Open questions

- The 35%/90% explanatory-power figures are stated without the regression detail in the post; the Hedge Fund Journal article carries the methodology.
- Classification thresholds (what counts as "bear regime") not specified here.

## Where this fits

- [[artur-sepp]] — author.
- [[risk-premia-alpha]] — the central metric, defined as excess return after adjusting for conditional beta exposures.
- [[regime-conditional-beta]] — the model's core device; resolves the "market-neutral" illusion.
- [[crisis-alpha]] — CTAs' protective negative bear betas; extends [[trend-following-tail-risk-hedging-alpha]].
- [[tail-risk-hedging]] — defensive vs risk-seeking classification.
- [[overfitting]] — the author's charge that ARP backtests were marketing-driven overfits.
