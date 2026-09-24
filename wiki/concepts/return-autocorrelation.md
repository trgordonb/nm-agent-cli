---
type: concept
title: "Return autocorrelation (as trend-following driver)"
tags: [trend-following, regime-analysis]
sources: [trend-following-tail-risk-hedging-alpha]
created: 2026-09-23
updated: 2026-09-24
graph:
  relationships:
    - predicate: depends_on
      object: concept:trend-following
      source: trend-following-tail-risk-hedging-alpha
      evidence: "The nature of trend-followers is to benefit from markets where prices and returns are auto-correlated, which implies the persistence of trends over longer time horizons."
      raw_ref: "raw/trend-following-tail-risk-hedging-alpha.md#L47"
      confidence: high
      status: current
---

# Return autocorrelation (as trend-following driver)

Trend-following profits exist because prices are autocorrelated — trends persist. Sepp operationalizes this: the 2011–2018 underperformance of trend-followers coincides with significantly **negative lag-1 autocorrelation** of monthly and quarterly S&P 500 returns — a mean-reverting regime under positive drift in which trend-followers should not, and did not, outperform ([[trend-following-tail-risk-hedging-alpha]]).

## Why it matters

- It converts "trend-following stopped working" from a mystery into a measurable regime variable — the same regime-first thinking as [[regime-conditional-beta]] and the cyclical rankings behind [[model-cycling]].
- Sepp introduces an alternative autocorrelation measure for short samples, claiming strong explanatory power for SG trend index returns — the potential basis for a trend-following regime filter.

## Open questions

- Single-source and author-specific methodology (the alternative measure is not defined in the post); sample ends 2018. Corroborating the autocorrelation→performance link on later data would upgrade this from hypothesis to finding.
