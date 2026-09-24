---
type: concept
title: "Smart beta"
tags: [smart-beta, crypto, portfolio-allocation]
sources: [crypto-smart-beta-strategies]
created: 2026-09-23
updated: 2026-09-24
graph:
  relationships:
    - predicate: depends_on
      object: concept:bootstrapping-simulation
      source: crypto-smart-beta-strategies
      evidence: "To overcome these challenges, I constructed a bootstrapping simulation engine which allows to generate joint paths of price and fundamental data for the empirical distributions without breaking the correlation and auto-correlation structure of dependencies in the data."
      raw_ref: "raw/crypto-smart-beta-strategies.md#L22"
      confidence: high
      status: current
---

# Smart beta

Systematic, rules-based index construction that captures a return driver (sector, factor, carry) in a transparent, investable product. Sepp's application is **sector-based smart beta indices for crypto assets** ([[crypto-smart-beta-strategies]]).

## Design constraints specific to crypto

1. **Data quality:** multiple providers with inconsistent data; public fundamentals (market cap, volumes) are themselves alpha-bearing rather than ambient context.
2. **Short history:** DeFi tokens mostly listed H2 2020 → ~1 year of data to validate risk-reward.
3. **Liquidity:** ~30 tier-one exchanges systematically over-report volumes; liquidity screening must be endogenous to the strategy.

The proposed methodological response is a bootstrapping simulation engine preserving correlation/autocorrelation structure ([[bootstrapping-simulation]]) — the short-sample analog of the out-of-sample discipline in [[backtest]] and [[overfitting]].

## Status

Framing-level only in the ingested source; index rules and results live in the video, not the post.
