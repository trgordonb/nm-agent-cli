---
type: concept
title: "Mean reversion (short-horizon equity)"
tags: [mean-reversion]
sources: [volume-and-mean-reversion]
created: 2026-09-23
updated: 2026-09-23
---

# Mean reversion (short-horizon equity)

Short-horizon equity strategies that buy sharp down-moves expecting a bounce. The ingested evidence is Alvarez's volume study ([[volume-and-mean-reversion]]): Russell 3000 stocks, 2-period [[rsi]] < 1 entries, RSI > 70 exits, 2007–2022.

## Findings

- **Low volume enhances the edge** — setups with volume in the bottom fifth of the last 20 days average materially higher per-trade P/L. Surprising direction: the prior expectation (and common intuition) favors high volume.
- But the edge is **scarce**: low-volume buckets hold only ~18% of trades; filtering to them collapses exposure from 25% to 5%.
- **Ranking beats filtering:** ranking low-volume signals higher preserves trade count and improves CAR/UI/avg-P&L/win-rate/Sharpe modestly — see [[trade-selection]].
- Trades below the 200-day MA are much weaker (+0.15% vs +0.54% above) — the reverse of the author's own production strategy, a regime-interaction caveat.

## Author's adoption decision

Not adopted: the improvement is too small to justify added rules — the complexity budget argument ([[parameter-robustness]]); useful instead for discretionary trade prioritization.
