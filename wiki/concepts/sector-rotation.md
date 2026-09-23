---
type: concept
title: "Sector rotation"
tags: [etf-rotation, momentum]
sources: [sector-rotation-trading-rules]
created: 2026-09-23
updated: 2026-09-23
---

# Sector rotation

Monthly cross-sectional rotation among sector ETFs (the nine SPDRs: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY) by trailing return. The ingested test ([[sector-rotation-trading-rules]]) replicated a published variant that buys ranks 4–6 rather than 1–3 and asked whether the rule "makes sense."

## Findings

- At 1-month ranking, buying 4–6 wins on CAR; ranks 1–3 are clearly worst (short-term reversal at the top); ranks 2–4 match 4–6 with better MDD/Sharpe.
- The pattern is **not robust**: at 3-month ranking ranks 1–3 win, at 6-month results converge — the middle-band edge is a ranking-window artifact.
- Post-2010 buy-and-hold SPY matches most rotation variants on CAR/Sharpe with none of the work.

## Interpretation

The rank-1-avoidance idea has a plausible causal story (overbought leadership), but the data say the choice of band is a tuneable, not a structure — a [[parameter-robustness]] case study within the [[momentum]] family, and a [[market-timing]]-genre caution about [[regime-analysis]] (the 2010s bull flattered everything).
