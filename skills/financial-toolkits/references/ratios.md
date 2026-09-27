# Ratios — 80+ efficiency, liquidity, profitability, solvency, valuation ratios

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/ratios

Access through a `Toolkit` instance: `companies.ratios.<function>()`.
Naming convention: `get_<snake_case_ratio>` (e.g. `get_return_on_equity()`),
plus one `collect_*` function per category that returns every ratio at once.

## Categories and collect functions

```python
companies.ratios.collect_efficiency_ratios()
companies.ratios.collect_liquidity_ratios()
companies.ratios.collect_profitability_ratios()
companies.ratios.collect_solvency_ratios()
companies.ratios.collect_valuation_ratios()
companies.ratios.collect_custom_ratios()  # ratios you defined on init
```

A `collect_*` result is also the fastest way to discover exact metric names
(they appear as row labels) without spending API quota on trial calls.

## Output shape (verified)

`collect_*_ratios()` returns a DataFrame with **ratios as rows** (Title Case,
e.g. "Cash Conversion Cycle") and **fiscal periods as columns** as a
`PeriodIndex` (`Y-DEC` for annual, quarterly `Q-DEC` when
`quarterly=True`). With multiple tickers, the ticker is an extra row-index
level; with a single ticker there is no ticker level at all.

Most recent fiscal year (and prior-year comparison):

```python
eff = companies.ratios.collect_efficiency_ratios()  # rows = ratios, cols = years
latest, prior = eff.columns[-1], eff.columns[-2]    # Periods, e.g. 2025, 2024
print(eff[[prior, latest]].dropna(how="all"))
```

Columns are fiscal years tied to each company's own calendar (NVDA's
Jan-ending year is labelled by the year it ends in).

## Representative methods (full list via collect_* or the docs page)

- **Efficiency**: asset turnover, inventory/receivables/payables turnover,
  operating & cash conversion cycles, working-capital turnover.
- **Liquidity**: current ratio, quick ratio, cash ratio, working capital.
- **Profitability**: gross / operating / net profit margins, return on equity
  (`get_return_on_equity`), return on assets, return on invested capital,
  income quality ratio, dividend paid & capital expenditure to revenue.
- **Solvency**: debt-to-asset / debt-to-capital / debt-to-equity ratios,
  interest and dividend coverage, net debt-to-EBITDA.
- **Valuation**: earnings yield, P/E, forward P/E, PEG, price-to-book,
  price-to-sales, EV-to-sales, EV-to-EBITDA, EV-to-free-cash-flow, buyback
  and shareholder yield.

## Cross-cutting parameters (see SKILL.md §4)

```python
companies.ratios.get_return_on_equity(growth=True, trailing=4, rolling=8)
```

Custom ratios: pass definitions to `Toolkit(..., ratios={...})` — see the
docs page section "Custom Ratios".
