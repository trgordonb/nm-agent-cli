---
type: entity
kind: person
title: "Artur Sepp"
aliases: ["artursepp"]
tags: [quant-researcher, volatility, trend-following]
sources: [allocation-to-systematic-volatility-strategies, machine-learning-for-volatility-trading, trend-following-tail-risk-hedging-alpha, trend-following-ctas-vs-arp-products, crypto-smart-beta-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Artur Sepp

Quantitative researcher and practitioner (blog at artursepp.com) whose work in this wiki centers on **volatility strategies, trend-following, and regime-conditional risk models**. Five of the ten currently ingested sources are his, spanning 2017–2022. He publishes both blog write-ups and SSRN papers, and presents at QuantMinds.

## Research themes across his sources

- **Volatility risk premia as an allocatable asset class** ([[allocation-to-systematic-volatility-strategies]]): put/strangle/VIX-futures carry strategies with statistical filtering and delta-hedging, showing filter+hedge variants reach insignificant market beta with significant alpha.
- **Machine learning for model selection in volatility forecasting** ([[machine-learning-for-volatility-trading]]): ~40 models across four classes; Hidden Markov Chains best in trends, intraday estimators best in ranges; dynamic model switching framed via minimum description length.
- **Trend-following as convex crisis protection** ([[trend-following-tail-risk-hedging-alpha]]): positive skew and convexity when measured at quarterly frequency; autocorrelation of index returns explains trend-following performance cycles.
- **Regime-conditional attribution vs ARP marketing** ([[trend-following-ctas-vs-arp-products]]): "market-neutral" claims dissolve under regime-conditional betas; CTAs are the anomaly — protective negative bear betas with insignificant risk-premia alpha.
- **Crypto smart beta design** ([[crypto-smart-beta-strategies]]): the data-quality/short-history/liquidity challenge triad and bootstrapping simulation as mitigation.

## Methodological signature

Sepp consistently argues that **unconditional performance statistics hide regime-conditional risk** — the same conviction behind both his delta-hedging result (beta vanishes after hedging) and his ARP critique (beta reappears in bear regimes). He is comfortable with model complexity (ML, HMC, bootstrapping engines) when it targets a measurable estimation problem.

## Related

Contrast with [[cesar-alvarez]], whose published work in this wiki is skeptical of exactly the kind of complexity Sepp deploys — though the two are complementary rather than contradictory: Sepp builds regime-aware models; Alvarez stress-tests whether simple rules survive parameter perturbation and out-of-sample checks. Both share the anti-overfitting instinct that anchors [[overfitting]] and [[parameter-robustness]].
