---
type: source
title: "Developing systematic smart beta strategies for crypto assets (QuantMinds presentation)"
authors: ["Artur Sepp"]
url: "https://artursepp.com/2022/02/23/developing-systematic-smart-beta-strategies-for-crypto-assets-quantminds-presentation/"
raw: "raw/crypto-smart-beta-strategies.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [crypto, smart-beta, backtest]
entities: [artur-sepp]
concepts: [smart-beta, bootstrapping-simulation, backtest]
---

# Developing systematic smart beta strategies for crypto assets (Sepp, 2022)

Video-post of Sepp's QuantMinds Barcelona (December 2021) talk: a framework for designing sector-based smart beta indices and products for diversified crypto investing. The post is short — it frames three structural challenges and the method used to address them.

## The three challenges

1. **Data quality:** crypto market data must be aggregated and filtered across many providers; unlike traditional assets, public data such as market cap and traded volumes can themselves be a source of alpha.
2. **Short history:** most DeFi protocol tokens listed in H2 2020, leaving roughly one year of data to establish a strategy's risk-reward profile.
3. **Liquidity:** crypto liquidity is thin versus traditional assets; ~30 tier-one exchanges systematically over-estimate traded volumes, so liquidity screening must be built into the strategy.

## Method

A **bootstrapping simulation engine** generating joint paths of price and fundamental data from empirical distributions while preserving correlation and autocorrelation structure — a response to the short-history problem (see [[bootstrapping-simulation]]).

## Open questions

- The post does not state the index construction rules, sector taxonomy, or results — those are in the video. Claims here are framing-level, not evidence-level.

## Where this fits

- [[artur-sepp]] — author.
- [[smart-beta]] — the index/product design paradigm.
- [[bootstrapping-simulation]] — the proposed answer to short samples.
- [[backtest]] — the short-history/data-quality caveats apply to any crypto backtest.
