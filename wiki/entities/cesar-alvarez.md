---
type: entity
kind: person
title: "Cesar Alvarez"
aliases: ["alvarez quant trading"]
tags: [quant-researcher, backtesting, research-methodology]
sources: [benford-law-strategy-selection, historical-volatility-parameter-adjustment, sector-rotation-trading-rules, spy-sso-tlt-strategy, volume-and-mean-reversion]
created: 2026-09-23
updated: 2026-09-24
graph:
  aliases: ["alvarez quant trading"]
  relationships:
    - predicate: authored
      object: source:benford-law-strategy-selection
      source: benford-law-strategy-selection
      evidence: 'author: "[[Cesar Alvarez]]"'
      raw_ref: "raw/benford-law-strategy-selection.md#L5"
      confidence: high
      status: current
    - predicate: authored
      object: source:historical-volatility-parameter-adjustment
      source: historical-volatility-parameter-adjustment
      evidence: 'author: "[[Cesar Alvarez]]"'
      raw_ref: "raw/historical-volatility-parameter-adjustment.md#L5"
      confidence: high
      status: current
    - predicate: authored
      object: source:sector-rotation-trading-rules
      source: sector-rotation-trading-rules
      evidence: 'author: "[[Cesar Alvarez]]"'
      raw_ref: "raw/sector-rotation-trading-rules.md#L5"
      confidence: high
      status: current
    - predicate: authored
      object: source:spy-sso-tlt-strategy
      source: spy-sso-tlt-strategy
      evidence: 'author: "[[Cesar Alvarez]]"'
      raw_ref: "raw/spy-sso-tlt-strategy.md#L5"
      confidence: high
      status: current
    - predicate: authored
      object: source:volume-and-mean-reversion
      source: volume-and-mean-reversion
      evidence: 'author: "[[Cesar Alvarez]]"'
      raw_ref: "raw/volume-and-mean-reversion.md#L5"
      confidence: high
      status: current
    - predicate: works_on
      object: concept:backtest
      source: spy-sso-tlt-strategy
      evidence: "It is easy to forget the step of removing rules. Removing the SSO rule shows that it was mostly adding volatility."
      raw_ref: "raw/spy-sso-tlt-strategy.md#L80"
      confidence: high
      status: current
    - predicate: works_on
      object: concept:overfitting
      source: benford-law-strategy-selection
      evidence: "My hypothesis was that failure to follow Benford''s Law implied a higher potential for curve fitting, which then implies that those in-sample runs in the top tercile for CAR and bottom tercile for Chi-Square Statistic would again end up in the top tercile for CAR in the out-of-sample."
      raw_ref: "raw/benford-law-strategy-selection.md#L62"
      confidence: high
      status: current
    - predicate: works_on
      object: concept:parameter-robustness
      source: historical-volatility-parameter-adjustment
      evidence: "Since I want to focus on testing since 2000, I calculated the 80% value for the 21-day historical volatility since 1999, because I wanted a year of data before the start of the test. The 80% value for this period is 21.2, which is substantially different from the 17 value used. This is a concern."
      raw_ref: "raw/historical-volatility-parameter-adjustment.md#L56"
      confidence: high
      status: current
---

# Cesar Alvarez

Independent quant trader and researcher (alvarezquanttrading.com) whose blog posts in this wiki form a coherent **research-methodology corpus**: replicate published strategies, stress the parameters, prefer simplicity, and document negative results. Five of the ten currently ingested sources are his, all built on AmiBroker with Norgate Data, spanning 2022–2024. He also trades dual-momentum and mean-reversion strategies referenced in passing.

## Research themes across his sources

- **Replication before belief:** every post starts by reproducing the published result ([[historical-volatility-parameter-adjustment]], [[sector-rotation-trading-rules]], [[spy-sso-tlt-strategy]]), then perturbs one assumption at a time.
- **Parameter fragility as disqualifier:** the HV-threshold strategy's edge lived in a static constant (17) that every look-ahead-free variant failed to reproduce ([[historical-volatility-parameter-adjustment]]); the "buy ranks 4,5,6" sector rule dissolved when the ranking length changed ([[sector-rotation-trading-rules]]); the VIX<25 cutoff proved non-special ([[spy-sso-tlt-strategy]]).
- **Rule removal as a discipline:** the SSO post's meta-lesson — builders add rules reflexively; testing removal showed leverage added volatility, not return ([[spy-sso-tlt-strategy]]).
- **Small edges vs complexity budget:** the volume finding was real but too small to justify added rules ([[volume-and-mean-reversion]]).
- **Negative results published openly:** Benford's Law strategy selection produced nothing ([[benford-law-strategy-selection]]); he publishes it anyway, with the methodological moral to test ideas on a second strategy before believing the first result.
- **Camp 1 on trading rules:** strategies need a high-level causal story he can hold onto during drawdowns; opaque, parameter-sensitive ML systems fail that test even with good stats ([[sector-rotation-trading-rules]]).

## Methodological signature

Test windows are deliberately recent (2000+, often 2007+ or 2010+), with the recurring observation that post-2010 bull markets make many rotation strategies barely beat buy-and-hold. He distinguishes CAR/Sharpe improvements from drawdown control, weighting MDD heavily.

## Related

See [[artur-sepp]] for the contrast in research style; both share the anti-overfitting instinct that anchors [[overfitting]] and [[parameter-robustness]].
