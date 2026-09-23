---
type: concept
title: "Volatility risk premia"
tags: [volatility, risk-premia]
sources: [allocation-to-systematic-volatility-strategies, trend-following-ctas-vs-arp-products]
created: 2026-09-23
updated: 2026-09-23
---

# Volatility risk premia

The persistent tendency of market-implied volatility to exceed subsequently realized volatility, which compensates sellers of options and volatility futures for bearing tail risk. Harvesting this premium is the profit engine of [[volatility-carry-strategies]] and the reason short-vol strategies have historically positive drift — and it is the *hidden tail exposure* that regime-conditional analysis exposes (see [[regime-conditional-beta]] and [[risk-premia-alpha]]).

## Evidence in this wiki

- [[allocation-to-systematic-volatility-strategies]] documents the premium across three instruments: ATM put selling (implied > realized at the money), strangles (skew and convexity premia out of the money), and VIX futures (contango roll yield ~90% annualized — see [[volatility-carry-strategies]]).
- [[trend-following-ctas-vs-arp-products]] shows the other side: the premium is compensation for crisis losses, so risk-premia alpha and marginal bear beta are nearly linearly related across hedge fund and ARP indices. The premium is real but never "free."

## Open questions

- All quantified evidence here comes from a single author ([[artur-sepp]]) with sample ending 2017–2019. Corroboration from independent sources would upgrade the claims.
