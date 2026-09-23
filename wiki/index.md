# Wiki Index

The catalog of all pages in this wiki. Each entry: a wikilink to the page and a one-line summary. The LLM reads this first when answering queries to identify candidate pages.

Keep summaries tight — one line each. The index is engineered to be cheap to read; a fat index defeats its purpose.

When this file exceeds ~300 lines or the wiki passes ~150 pages, shard into `wiki/indexes/<type>.md` and replace this file with a directory of shards. See the `scaling-playbook.md` reference in the `llm-wiki` skill for the migration procedure.

---

## Sources

Ingested raw sources, one summary page each. Raw files live in `raw/`.

- [[allocation-to-systematic-volatility-strategies]] — Sepp 2017: three vol-carry strategies × hedging variants; filter doubles Sharpe, delta-hedging kills beta; 10% allocation lifts portfolio alpha ~1%.
- [[machine-learning-for-volatility-trading]] — Sepp 2018: ~40 vol models + ML selection; HMC best in trends, intraday estimators in ranges; MDL framing.
- [[trend-following-tail-risk-hedging-alpha]] — Sepp 2018: trend-following's skew/convexity profile, quarterly measurement, autocorrelation as the performance driver, allocation math.
- [[trend-following-ctas-vs-arp-products]] — Sepp 2019: regime-conditional CAPM; risk-seeking vs defensive vs CTA anomaly; the 2018 ARP failure explained.
- [[crypto-smart-beta-strategies]] — Sepp 2022: crypto smart beta design challenges (data quality, short history, liquidity) and bootstrapping simulation.
- [[benford-law-strategy-selection]] — Alvarez 2022: negative result — Benford compliance fails as a curve-fit detector; methodology lessons.
- [[historical-volatility-parameter-adjustment]] — Alvarez 2022: HV-conditional timing replicates but every look-ahead-free threshold variant collapses; fragility disqualifies.
- [[sector-rotation-trading-rules]] — Alvarez 2023: "buy ranks 4,5,6" is a ranking-length artifact; camp-1 argument for comprehensible rules.
- [[spy-sso-tlt-strategy]] — Alvarez 2024: SSO leverage adds volatility not return; TLT-MA→cash rule fixes the 2022 bond bear; test rule removal.
- [[volume-and-mean-reversion]] — Alvarez 2022: low volume (percent-rank) enhances mean-reversion edge but too small to adopt; rank beats filter.

## Entities

- [[artur-sepp]] — quant researcher (artursepp.com): volatility strategies, trend-following, regime-conditional risk, ML for model selection; 5 sources.
- [[cesar-alvarez]] — independent quant (alvarezquanttrading.com): replication, parameter robustness, published negative results; 5 sources.

## Concepts

### Volatility
- [[volatility-risk-premia]] — implied > realized volatility as harvestable premium; real but never free (paid in tail risk).
- [[volatility-carry-strategies]] — short put / strangle / VIX-futures trio; profit sources and tail behavior.
- [[delta-hedging]] — removes market beta, concentrates tail risk; makes vol strategies alpha-like.
- [[statistical-filtering]] — roll gate re-fit on prior data; doubled Sharpe in backtest; strongest filter evidence here.
- [[volatility-targeting]] — 10% vol rescaling for comparability and allocation; amplifies model-choice bias (Lo's 40x).
- [[volatility-forecasting]] — model-selection-centric view; 200–300 candidate families; forecast quality is load-bearing.
- [[volatility-estimators]] — measurement layer; simple intraday estimators win in range-bound regimes.
- [[volatility-filtering]] — HV/VIX gates for timing decisions; two implementations, fragile verdicts.
- [[hidden-markov-models]] — best-in-class vol forecaster across asset classes; regime-dependent edge.

### Machine learning & model selection
- [[machine-learning-for-trading]] — supervised/unsupervised/RL taxonomy applied to trading; Sepp's pro vs Alvarez's opacity objection.
- [[model-cycling]] — model rankings rotate with regime; adaptive selection layer; also visible in trading-rule parameters.
- [[minimum-description-length]] — best model compresses data best; principled anti-overfitting for model zoos.

### Risk & regimes
- [[regime-conditional-beta]] — per-regime betas; classifies strategies risk-seeking/defensive/CTA; kills "market-neutral" claims.
- [[risk-premia-alpha]] — excess return after conditional-beta adjustment; linear in marginal bear beta; CTAs the anomaly.
- [[crisis-alpha]] — stress-period performance via trend adaptation or inverted carry; boundary conditions documented.
- [[convexity]] — skew + curvature as strategy risk metrics; trend-followers uniquely combine positive convexity with positive returns.
- [[tail-risk-hedging]] — candidate hedges compared; trend-following 50/50 halves risk-parity drawdown; TLT is not unconditional hedge.
- [[return-autocorrelation]] — lag-1 autocorrelation regime explains trend-following cycles; negative 2011–2018.
- [[stock-bond-correlation]] — 2022 joint bear broke TLT-as-hedge assumptions; double-MA gate response.
- [[regime-analysis]] — umbrella term for regime-conditional evaluation across all sources.

### Strategies
- [[trend-following]] — CTA risk profile: positive skew/convexity, speed half-lives, the CTA anomaly, autocorrelation driver.
- [[market-timing]] — monthly ETF rotation genre: three studies, drawdown control is the real product, buy-and-hold is the baseline to beat.
- [[sector-rotation]] — SPDR monthly rotation; middle-band rule is an artifact; 2010s bull flattered the genre.
- [[momentum]] — cross-sectional and time-series roles; trend-following vs stock momentum convexity contrast.
- [[mean-reversion]] — RSI(2) short-horizon equity; low-volume edge; regime interaction with 200-day MA.
- [[rsi]] — RSI(2) entry/exit engine used as the baseline in the volume study.
- [[smart-beta]] — rules-based index products; crypto-specific design constraints.
- [[bootstrapping-simulation]] — resampled joint paths preserving dependence structure; answer to one-year crypto histories.
- [[moving-average-filter]] — 200-day trend gate; sturdy itself, fragile in combination; hedge-leg variant.
- [[volume-filters]] — percent-rank volume; low volume enhances mean-reversion; rank beats filter.

### Research methodology
- [[overfitting]] — the master concept: five detection approaches catalogued across all sources.
- [[parameter-robustness]] — edges must survive parameter perturbation; four audited cases, three failures.
- [[look-ahead-bias]] — calibration leakage; point-in-time recomputation as the test; soft variant via unconditional aggregation.
- [[backtest]] — collective practice: replicate, perturb, recent windows, rule removal, MDD-weighted reporting.
- [[research-methodology]] — both authors' working epistemology extracted; convergence despite style differences.
- [[trade-selection]] — filtering vs ranking signal-quality modifiers; complexity budget as third axis.
- [[benfords-law]] — leading-digit distribution; prerequisite mismatch with returns; three methodological lessons.

## Synthesis

(populated as query answers are filed back)
