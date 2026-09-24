---
type: entity
kind: person
title: "Artur Sepp"
aliases: ["artursepp"]
tags: [quant-researcher, volatility, trend-following]
sources: [allocation-to-systematic-volatility-strategies, machine-learning-for-volatility-trading, trend-following-tail-risk-hedging-alpha, trend-following-ctas-vs-arp-products, crypto-smart-beta-strategies]
created: 2026-09-23
updated: 2026-09-24
graph:
  aliases: [artursepp]
  relationships:
    - predicate: authored
      object: source:allocation-to-systematic-volatility-strategies
      source: allocation-to-systematic-volatility-strategies
      evidence: 'author: "[[artursepp]]"'
      raw_ref: "raw/allocation-to-systematic-volatility-strategies.md#L5"
      confidence: high
      status: current
    - predicate: authored
      object: source:machine-learning-for-volatility-trading
      source: machine-learning-for-volatility-trading
      evidence: 'author: "[[artursepp]]"'
      raw_ref: "raw/machine-learning-for-volatility-trading.md#L5"
      confidence: high
      status: current
    - predicate: authored
      object: source:trend-following-tail-risk-hedging-alpha
      source: trend-following-tail-risk-hedging-alpha
      evidence: 'author: "[[artursepp]]"'
      raw_ref: "raw/trend-following-tail-risk-hedging-alpha.md#L5"
      confidence: high
      status: current
    - predicate: authored
      object: source:trend-following-ctas-vs-arp-products
      source: trend-following-ctas-vs-arp-products
      evidence: 'author: "[[artursepp]]"'
      raw_ref: "raw/trend-following-ctas-vs-arp-products.md#L5"
      confidence: high
      status: current
    - predicate: authored
      object: source:crypto-smart-beta-strategies
      source: crypto-smart-beta-strategies
      evidence: 'author: "[[artursepp]]"'
      raw_ref: "raw/crypto-smart-beta-strategies.md#L5"
      confidence: high
      status: current
    - predicate: works_on
      object: concept:volatility-carry-strategies
      source: allocation-to-systematic-volatility-strategies
      evidence: "I present a few systematic strategies for investing into volatility risk-premia and illustrate their back-tested performance."
      raw_ref: "raw/allocation-to-systematic-volatility-strategies.md#L12"
      confidence: high
      status: current
    - predicate: works_on
      object: concept:volatility-forecasting
      source: machine-learning-for-volatility-trading
      evidence: "Recently I have been working on applying machine learning for volatility forecasting and trading."
      raw_ref: "raw/machine-learning-for-volatility-trading.md#L12"
      confidence: high
      status: current
    - predicate: works_on
      object: concept:trend-following
      source: trend-following-tail-risk-hedging-alpha
      evidence: "Using the trend system parametrized by the half-life of the trend smoothing, I analyze at which frequency of returns measurement the trend-following strategy can generate the positive convexity."
      raw_ref: "raw/trend-following-tail-risk-hedging-alpha.md#L59"
      confidence: high
      status: current
    - predicate: works_on
      object: concept:smart-beta
      source: crypto-smart-beta-strategies
      evidence: "I presented a framework for the design of sector-based smart beta indices and products for diversified investing to crypto assets."
      raw_ref: "raw/crypto-smart-beta-strategies.md#L14"
      confidence: high
      status: current
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
