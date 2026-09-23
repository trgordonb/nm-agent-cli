---
type: concept
title: "Overfitting (and its detection)"
tags: [overfitting, research-methodology, backtest]
sources: [benford-law-strategy-selection, historical-volatility-parameter-adjustment, sector-rotation-trading-rules, machine-learning-for-volatility-trading, trend-following-ctas-vs-arp-products, volatility-targeting]
created: 2026-09-23
updated: 2026-09-23
---

# Overfitting (and its detection)

Fitting a strategy or model to historical noise such that backtest performance will not survive new data. The most cross-cutting concept in this wiki: every source touches it from a different angle.

## Detection attempts documented here

- **Statistical fingerprints of returns:** Benford's Law compliance of a strategy's daily returns was tested as a curve-fit detector — the hypothesis failed on a second strategy (the promising momentum result was direction-flipped and then vanished; see [[benfords-law]]). Moral: validate a detection idea on more than one strategy before believing it.
- **Parameter sensitivity scans:** if only one narrow parameter window works — 17 being both best-CAR and best-MDD in the HV test — treat the edge as suspect ([[parameter-robustness]], [[historical-volatility-parameter-adjustment]]); the VIX<25 cutoff that "seems too high" turned out to be one arbitrary point on a smooth frontier ([[spy-sso-tlt-strategy]]).
- **Look-ahead elimination:** recompute calibrated thresholds point-in-time; if results collapse toward buy-and-hold, the edge was calibration leakage ([[look-ahead-bias]], [[historical-volatility-parameter-adjustment]]).
- **Regime disaggregation:** unconditional smoothness can hide tail risk; ARP products sold as market-neutral were, under regime-conditional betas, paid short-tail positions whose backtests aggregated away the crisis regime ([[regime-conditional-beta]], [[trend-following-ctas-vs-arp-products]]).
- **Model-count discipline:** with 200–300 candidate volatility models, optimizing inside a [[volatility-targeting]] strategy can manufacture 40x apparent outperformance; ML-based out-of-sample selection and MDL compression are Sepp's mitigations ([[machine-learning-for-volatility-trading]], [[minimum-description-length]]).

## Practical synthesis

| Threat | Test that exposed it |
| --- | --- |
| Curve-fit rules | Second-strategy replication ([[benfords-law]]) |
| Fragile constants | Parameter scans / dynamic recompute |
| Calibration leakage | Point-in-time thresholds |
| Hidden tail risk | Regime-conditional betas |
| Model selection bias | Out-of-sample model cycling |

Both authors converge here from opposite styles: Alvarez refuses complexity that can't explain itself; Sepp builds complexity but disciplines it with out-of-sample selection. See also [[backtest]].
