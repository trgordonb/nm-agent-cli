---
type: concept
title: "Trend following"
tags: [trend-following, cta, momentum]
sources: [trend-following-tail-risk-hedging-alpha, trend-following-ctas-vs-arp-products]
created: 2026-09-23
updated: 2026-09-23
---

# Trend following

Systematic strategies that hold positions in the direction of the prevailing price trend, with position size adapting as the trend signal evolves. In this wiki the subject is institutional trend-following (CTA indices: SG, BTOP50), where Sepp's work establishes the risk profile and the allocation case.

## Risk profile

- **Positive skewness and convexity** to equity indices — large gains in very bearish *and* very bullish markets — but only when returns are measured at frequencies exceeding the trend smoothing half-life and rebalancing period; quarterly is the recommended evaluation frequency ([[trend-following-tail-risk-hedging-alpha]]). See [[convexity]].
- **Speed matters:** fast smoothing (half-life < quarter) protects in sharp reversals but bleeds in choppy markets; medium/slow smoothing (quarter to year) suits long-horizon alpha. A 4-month half-life replicates SG/BTOP50 correlation from the 2000s.
- **The CTA anomaly:** under [[regime-conditional-beta]] CTAs show protective negative bear betas with insignificant [[risk-premia-alpha]] — neither tail-risk sellers nor paid insurance, but actively managed defense ([[trend-following-ctas-vs-arp-products]]). This is [[crisis-alpha]] by adaptation.

## What drives returns

Trend-followers profit from autocorrelated prices. The 2011–2018 SG index slump coincides with significantly negative lag-1 autocorrelation of S&P 500 monthly/quarterly returns — a mean-reverting regime under positive drift ([[return-autocorrelation]], [[trend-following-tail-risk-hedging-alpha]]).

## Distinctions

Trend-following produces *positive* convexity while stock momentum produces negative convexity; trend-following has stronger exposure to the autocorrelation factor ([[trend-following-tail-risk-hedging-alpha]]). Not to be confused with the [[momentum]] factor in equity cross-sections.
