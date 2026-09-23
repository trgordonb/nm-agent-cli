---
type: entity
kind: person
title: "Cesar Alvarez"
aliases: ["alvarez quant trading"]
tags: [quant-researcher, backtesting, research-methodology]
sources: [benford-law-strategy-selection, historical-volatility-parameter-adjustment, sector-rotation-trading-rules, spy-sso-tlt-strategy, volume-and-mean-reversion]
created: 2026-09-23
updated: 2026-09-23
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
