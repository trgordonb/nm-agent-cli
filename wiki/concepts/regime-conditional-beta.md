---
type: concept
title: "Regime-conditional beta"
tags: [regime-analysis, risk-premia, tail-risk]
sources: [trend-following-ctas-vs-arp-products, allocation-to-systematic-volatility-strategies, trend-following-tail-risk-hedging-alpha]
created: 2026-09-23
updated: 2026-09-23
---

# Regime-conditional beta

Measuring a strategy's market beta *per market regime* (bear / normal / bull) instead of unconditionally. Sepp's regime-conditional CAPM uses the marginal bear-market beta as the price of tail risk and yields the wiki's sharpest classification of systematic strategies ([[trend-following-ctas-vs-arp-products]]):

| Class | Marginal bear beta | Risk-premia alpha | Examples |
| --- | --- | --- | --- |
| Risk-seeking | Positive (risk rises in bears) | Positive, roughly linear in bear beta | Most HF and ARP indices; [[volatility-carry-strategies]] |
| Defensive | Negative (risk falls in bears) | Negative (you pay for protection) | Long-vol style products |
| Trend-following CTAs | Negative | **Insignificant** (the anomaly) | SG trend index constituents |

## What it explains

- **The "market-neutral" illusion:** unconditional statistics aggregate across regimes. A delta-hedged short put ([[delta-hedging]]) shows small normal-regime beta but significant crisis beta via negative gamma/vega; 2018 exposed this across ARP products (HFR Bank Systematic Risk-premia Multi-Asset −18% vs S&P 500 −4%).
- **The CTA anomaly:** CTAs combine defensive-style bear betas with no alpha penalty — active adaptation rather than static exposure. See [[crisis-alpha]] and [[trend-following]].
- **Allocation discipline:** evaluate risk-premia products only over samples containing both bull and bear regimes.

## Open questions

- The model explains ~90% of risk-premia for volatility strategies but only ~35% for HF/ARP products; regime definitions are not given in the post. Methodology lives in the Hedge Fund Journal article.
