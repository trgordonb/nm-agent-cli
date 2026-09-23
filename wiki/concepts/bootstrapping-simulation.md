---
type: concept
title: "Bootstrapping simulation (for short histories)"
tags: [backtest, simulation]
sources: [crypto-smart-beta-strategies]
created: 2026-09-23
updated: 2026-09-23
---

# Bootstrapping simulation (for short histories)

Generating many joint price/fundamental paths by resampling from empirical distributions while **preserving correlation and autocorrelation structure** — Sepp's answer to crypto's one-year-of-data problem ([[crypto-smart-beta-strategies]]). Instead of a single historical path, strategy evaluation runs over a distribution of plausible paths, trading historical fidelity for variance reduction.

## Where it fits

The short-sample complement to the out-of-sample disciplines in [[backtest]]: when you cannot add history, you add simulated variance around the history you have. Related in spirit to Sepp's other robustness devices — re-fitting filters strictly out-of-sample ([[statistical-filtering]]) and ML model selection ([[model-cycling]]).

## Status

Mentioned as the constructed engine in a video-summary post; implementation detail and validation are not in the ingested source. Single-source; hedge accordingly.
