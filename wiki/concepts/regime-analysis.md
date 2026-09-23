---
type: concept
title: "Regime analysis"
tags: [regime-analysis, research-methodology]
sources: [trend-following-ctas-vs-arp-products, trend-following-tail-risk-hedging-alpha, machine-learning-for-volatility-trading, sector-rotation-trading-rules, spy-sso-tlt-strategy, allocation-to-systematic-volatility-strategies, volume-and-mean-reversion]
created: 2026-09-23
updated: 2026-09-23
---

# Regime analysis

The umbrella practice of evaluating strategies, models, and parameters *conditional on the market state they operate in*, rather than on unconditional full-sample statistics. It is the deepest common thread across both authors in this wiki, appearing at four levels of formality:

1. **Formal regime-conditional models:** Sepp's regime-conditional CAPM with marginal bear betas classifies every systematic strategy as risk-seeking, defensive, or the CTA anomaly ([[regime-conditional-beta]]) — and recharacterizes unconditional "alpha" as tail-risk compensation ([[risk-premia-alpha]]).
2. **Regime-dependent model rankings:** HMC volatility models win in trends, intraday estimators in ranges — so model selection must be regime-aware ([[model-cycling]], [[hidden-markov-models]]).
3. **Explicit gates and filters:** 200-day MA regime tests, HV thresholds, VIX levels — coarse regime variables embedded in strategy rules ([[moving-average-filter]], [[volatility-filtering]]), whose fragility under recalibration is itself a finding ([[parameter-robustness]], [[look-ahead-bias]]).
4. **Sample-window sensitivity:** Alvarez's insistence on re-testing published backtests on recent windows is regime analysis in its simplest form — the post-2010 bull regime flattered rotation and timing strategies broadly ([[market-timing]], [[sector-rotation-trading-rules]]).

## Corollaries

- **Strategy–regime interaction:** mean-reversion trade quality differs above vs below the 200-day MA, in the *reverse* direction of the author's production strategy ([[mean-reversion]]) — edges are conditional even when the strategy is not explicitly regime-switched.
- **Correlation regimes:** stock-bond diversification failed in 2022; hedges need their own regime tests ([[stock-bond-correlation]]).
- **Performance explanations:** trend-following's 2011–2018 slump maps to a negative-autocorrelation regime ([[return-autocorrelation]]); the 2018 ARP collapse maps to hidden tail exposure materializing ([[trend-following-ctas-vs-arp-products]]).

## Where this fits

The quantified core is [[regime-conditional-beta]]; the adaptive responses are [[model-cycling]] and [[crisis-alpha]]; the failure modes of naive regime variables are covered under [[parameter-robustness]].
