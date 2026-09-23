---
type: source
title: "Machine Learning for Volatility Trading"
authors: ["Artur Sepp"]
url: "https://artursepp.com/2018/05/29/machine-learning-for-volatility-trading/"
raw: "raw/machine-learning-for-volatility-trading.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [volatility, machine-learning, forecasting, model-selection]
entities: [artur-sepp, andrew-lo]
concepts: [volatility-forecasting, volatility-estimators, hidden-markov-models, machine-learning-for-trading, minimum-description-length, model-cycling]
---

# Machine Learning for Volatility Trading (Sepp, 2018)

QuantMinds 2018 presentation (SSRN 3186401) on using machine learning for volatility forecasting and trading. The core problem: realized volatility is unobservable and must be inferred from price/tick data, with an estimated 200–300 competing model families available, so model *selection* becomes a first-class problem — Andrew Lo's "What is an Index" shows that optimizing a volatility model under a vol-targeting strategy on the S&P 500 can produce apparent outperformance of 40x versus the index, i.e., severe backtest bias risk.

## Approach

1. Implement ~40 volatility models across four classes: intraday estimators, GARCH-type, Bayesian, and Hidden Markov Chain (HMC).
2. Supervised learning per model: regression-based out-of-sample tests of each model's forecast quality.
3. Reinforcement learning as aggregation: dynamically select the best-performing model out-of-sample, weighting test results analogously to web-search ranking to produce forecasts for specific trading algorithms.

## Key findings

- Hidden Markov Chain models are among the best volatility forecasters across many asset classes.
- Model rankings are *cyclical*: HMC models perform best in strong-trend periods; simple intraday estimators perform best in range-bound markets. The ML layer's job is to detect the current regime and switch models accordingly.
- MDL connection: choosing the best volatility model is framed as minimum-description-length model selection — the best model compresses the data best (Kolmogorov complexity lens), which reduces computational complexity of the modeling.

## Open questions

- The post summarizes the talk; the SSRN paper has the model-level detail (which 40 models, test construction, aggregation weights).
- The regime-switching claim ("HMC in trends, intraday estimators in ranges") is asserted from presentation experience, not shown with tables in the post itself — hedge until the paper corroborates.

## Where this fits

- [[artur-sepp]] — author.
- [[volatility-forecasting]] — the problem being solved.
- [[volatility-estimators]] — one of the four model classes.
- [[hidden-markov-models]] — the standout model family.
- [[machine-learning-for-trading]] — the three-branch ML taxonomy and its application.
- [[minimum-description-length]] — the theoretical framing for model selection.
- [[model-cycling]] — the cyclical-ranking / dynamic-selection finding.
