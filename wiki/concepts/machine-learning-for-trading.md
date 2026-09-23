---
type: concept
title: "Machine learning for trading"
tags: [machine-learning, research-methodology]
sources: [machine-learning-for-volatility-trading, sector-rotation-trading-rules]
created: 2026-09-23
updated: 2026-09-23
---

# Machine learning for trading

The application of learning algorithms to market data, which Sepp's taxonomy splits into three branches ([[machine-learning-for-trading]] source: [[machine-learning-for-volatility-trading]]):

1. **Supervised learning** — fitting predictions from labeled history (regression-style); used to score each volatility model's out-of-sample forecast quality.
2. **Unsupervised learning** — structure discovery without labeled targets: clustering/factor analysis (PCA as canonical example) and deep learning; the deep-learning branch assigns weights to signals through layers.
3. **Reinforcement learning** — maximizing reward over a sequence of actions (Markov decision process formalism); used as the aggregation layer that dynamically selects the best volatility model out-of-sample.

## The two-sided verdict in this wiki

- **For (Sepp):** ML reduces backtest bias and improves live performance when it targets a well-posed estimation problem ([[volatility-forecasting]], [[model-cycling]], [[minimum-description-length]]). The framework "continuously learns from performance and new data" rather than fixing one model.
- **Against (Alvarez):** ML-driven strategies are "very opaque on understanding how parameters were selected and are usually parameter sensitive. This I would not trade" ([[sector-rotation-trading-rules]]). His camp-1 position requires a high-level causal story that opacity destroys.

Both positions coexist: Sepp's ML selects among *interpretable* statistical models with explicit out-of-sample tests; Alvarez's objection targets opaque parameter search. See [[overfitting]] for the shared enemy.
