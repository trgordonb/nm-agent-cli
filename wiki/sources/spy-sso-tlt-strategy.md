---
type: source
title: "SPY, SSO and TLT Strategy"
authors: ["Cesar Alvarez"]
url: "https://alvarezquanttrading.com/blog/spy-sso-and-tlt-strategy/"
raw: "raw/spy-sso-tlt-strategy.md"
ingested: 2026-09-23
created: 2026-09-23
updated: 2026-09-23
tags: [market-timing, etf-rotation, leverage, negative-result]
entities: [cesar-alvarez]
concepts: [market-timing, moving-average-filter, volatility-filtering, parameter-robustness, stock-bond-correlation]
---

# SPY, SSO and TLT Strategy (Alvarez, 2024)

Alvarez tests a reader-submitted monthly rotation between stocks and bonds whose distinguishing feature is leverage: hold SSO (2x S&P 500) when the market is bullish *and* calm. Rules: at the last trading day's close, if SPY > its 200-day MA hold TLT otherwise; if SPY > MA and VIX < 25 hold SSO, else SPY. His immediate read: the strategy predates the 2022 bond bear market (it assumes TLT is always the right bear-market asset) and the VIX cutoff of 25 looks too high. Tested 2007-01–2024-09.

## Iterations and findings

1. **Initial rules:** CAR slightly better than buy-and-hold, drawdown greatly reduced. Good first impression.
2. **TLT filter added:** if SPY is below its 200-day MA *and* TLT is below its own, hold cash (SHY tested marginally worse). Huge MDD improvement with slight CAR change. The 2022 stock-bond joint bear market broke the "TLT is the bear-market asset" assumption — "2022 fixed that illusion" of unconditional stock/bond diversification.
3. **VIX threshold scan:** lower cutoffs raise CAR via more SSO exposure but inflate drawdowns; higher cutoffs hold returns with lower drawdowns. The 25 value is not special.
4. **SSO removed:** reverting to an unlevered SPY/TLT/cash version cuts CAR ~1 point but MDD ~5 points. "Sometimes, simple is better."

## Meta-lesson recorded by the author

Strategy builders habitually *add* rules; the discipline of testing rule *removal* is easy to forget. Here removal showed the SSO leverage rule mostly added volatility, not return.

## Where this fits

- [[cesar-alvarez]] — author.
- [[market-timing]] — the genre.
- [[moving-average-filter]] — the 200-day MA regime test, applied to both SPY and TLT.
- [[volatility-filtering]] — the VIX-level bull/calm condition.
- [[parameter-robustness]] — the VIX threshold scan; 25 is not magic.
- [[stock-bond-correlation]] — the 2022 joint bear market that invalidated TLT-as-hedge assumptions.
