---
type: concept
title: "Minimum description length"
tags: [machine-learning, research-methodology, theory]
sources: [machine-learning-for-volatility-trading]
created: 2026-09-23
updated: 2026-09-23
---

# Minimum description length (MDL)

A model-selection principle: the best model of data is the one that compresses it best. Sepp connects volatility model choice to MDL — the best model is the shortest program that reproduces the data, and Kolmogorov complexity decomposes as: program to produce the model + program to produce the data given the model + a logarithmic term that becomes negligible with many data points ([[machine-learning-for-volatility-trading]]).

## Why it matters for trading

It gives a principled answer to the 200–300-model embarrassment of riches in [[volatility-forecasting]]: prefer the model whose total description (model + residuals) is shortest, which penalizes overfitting without arbitrary holdouts. It is the theoretical sibling of the practical anti-[[overfitting]] instincts in this wiki — Alvarez's "would I be comfortable trading this?" test is an informal compression prior on strategy complexity.

## Open questions

- Single-source; Sepp asserts the connection without worked examples in the post.
