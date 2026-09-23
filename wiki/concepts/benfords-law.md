---
type: concept
title: "Benford's Law"
tags: [research-methodology, statistics]
sources: [benford-law-strategy-selection]
created: 2026-09-23
updated: 2026-09-23
---

# Benford's Law

The empirical law that in many natural datasets the leading significant digit follows a logarithmic distribution — "1" is most frequent (~30%), "9" least (~5%). Famously used for fraud detection, which motivated testing it as a curve-fit detector: a curve-fit strategy's return stream might fail Benford compliance where genuine edges pass ([[benford-law-strategy-selection]]).

## Applicability prerequisites

1. Several orders of magnitude between smallest and largest values
2. Minimum or maximum unbounded
3. Thousands of observations
4. Data not concentrated around the mean

Daily percentage stock returns violate condition 4 — the documented empirical results confirm the mismatch: SPY 2007–2021 Chi-Square 17.9 (vs 15.5 conventional cutoff), S&P 500 constituents averaging 44.4, and strategy-optimization return streams at 210–2143, far outside compliance.

## The lesson recorded

The strategy-selection hypothesis failed — on momentum a diagonal pattern appeared but in the opposite direction, on mean reversion nothing. The methodological residue is more valuable than the result: (a) check data-prerequisite fit *before* running the clever test; (b) verify an apparent pattern on a second strategy before building a story around it; (c) a statistically interesting result with no causal story is not tradable. All three feed [[overfitting]] and [[research-methodology]] thinking.
