---
type: concept
title: "Volume filters"
tags: [volume, trade-selection, mean-reversion]
sources: [volume-and-mean-reversion]
created: 2026-09-23
updated: 2026-09-23
---

# Volume filters

Using traded volume to modify signal quality. Alvarez's prior attempts (current volume ÷ 20-day average or median) found nothing; the variant that worked is the **percent rank of volume over the last 20 days** (`PercentRank(V,20)` in AmiBroker) — a rank-based, distribution-free normalization ([[volume-and-mean-reversion]]).

## The result

- Low percent-rank (bottom ~40%) setups beat the average trade by ~18% above the 200-day MA; the effect is stronger below it. Direction is *contrarian to volume*: quiet setups mean-revert better.
- As a hard filter (<20) it boosts per-trade P/L from 1.87% → 2.58% but cuts exposure 25% → 5%. As a *ranking preference* it keeps trade count and adds small, broad improvements.

## Adoption logic

A real but small edge fails the complexity budget for a systematic add-on ([[parameter-robustness]], [[trade-selection]]), yet is genuinely useful for discretionary prioritization and sizing. Single-source finding; corroboration on other mean-reversion engines (and on why low volume predicts bounce quality) is open.
