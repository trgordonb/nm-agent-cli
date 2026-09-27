---
name: edgar
description: "Work with SEC EDGAR filings in Python using the EdgarTools library (pip package: edgartools). Use this skill whenever the user mentions SEC filings, EDGAR, 10-K, 10-Q, 8-K, 13F, Form 4, insider trading, institutional holdings, proxy statements, XBRL financial data, filing analysis, corporate disclosures, or wants financial statements or company data from the SEC — even if they don't name a library. Covers company lookup, financial statements, filing search/filtering, typed data objects, insider trades, hedge fund portfolios, and XBRL facts."
---

# Edgar — SEC EDGAR analysis with EdgarTools

EdgarTools (`pip install edgartools`) turns SEC EDGAR filings into typed Python objects and pandas DataFrames. Free, no API key. This skill gives you the working patterns; read the reference files only when you need them.

## Setup (always required)

The SEC requires every request to carry an identity — no key, no signup, just a name and email:

```bash
export EDGAR_IDENTITY="John Doe john.doe@company.com"   # or set_identity() in Python
```

```python
from edgar import *
set_identity("John Doe john.doe@company.com")  # if env var not set
```

Install: `pip install edgartools` — but import it as `edgar` (`from edgar import *`). There is no importable module named `edgartools`.

**Wrong package warning:** If you see `ImportError: cannot import name 'get_filings' from 'edgar'`, the unrelated `edgar` PyPI package is installed. Fix: `pip uninstall edgar && pip install edgartools`.

## The mental model

Everything starts with a `Company` or a `Filing`. The core pattern:

```python
from edgar import Company

company = Company("AAPL")                        # by ticker, CIK, or name
filings = company.get_filings(form="10-K")       # filter filings
filing = filings.latest()                        # pick one
tenk = filing.obj()                              # parse into typed object
```

`.obj()` returns a form-specific typed object (TenK, Form4, ThirteenF, EightK, ...) whose data is available as properties and DataFrames.

## Choosing the right API (most common confusion)

| I want to... | Use |
|---|---|
| Revenue, net income, balance sheet, cash flow | `company.get_financials()` — covers 95% of cases |
| Quarterly financials | `company.get_quarterly_financials()` |
| 4+ years of historical trends for a concept | `company.get_facts()` |
| Segment breakdowns / footnotes / one filing's XBRL | `filing.xbrl()` (can return None — check) |
| Insider trades / holdings / events / sections | `filing.obj()` on the appropriate form |

Do NOT parse `filing.xbrl()` statements manually when `get_financials()` would do — XBRL concept names vary by company (e.g. "Revenues" vs "RevenueFromContractWithCustomer..."); `get_financials()` normalizes them.

## Core workflow

```python
financials = Company("MSFT").get_financials()
financials.income_statement()      # multi-period, XBRL-stitched
financials.balance_sheet()
financials.cash_flow_statement()   # canonical name; cashflow_statement() aliases work
financials.get_revenue()           # integer in ACTUAL dollars, e.g. 391035000000
financials.get_net_income(period_offset=1)  # prior year; offset 0 = current
financials.income_statement().to_dataframe()   # call to_dataframe() on the STATEMENT, not on financials
```

**Statement DataFrame shape:** wide format — one row per XBRL concept, columns are period labels like `'2026-07-26 (Q2)'`, `'2026-01-25 (FY)'`, `'2026-07-26 (YTD)'`, plus metadata columns (concept, label, level, abstract, ...). There are no long-format `end`/`value`/`uom` columns. Filter rows by `concept` (e.g. `df[df['concept'] == 'us-gaap_NetIncomeLoss']`) and pick period-label columns.

**Quick getters on Financials:** exactly these — `get_revenue`, `get_net_income`, `get_operating_income`, `get_shares_outstanding_basic`, `get_shares_outstanding_diluted`, `get_total_assets`, `get_total_liabilities`, `get_stockholders_equity`, `get_current_assets`, `get_current_liabilities`, `get_operating_cash_flow`, `get_capital_expenditures`, `get_free_cash_flow`, `get_currency_symbol`, `get_financial_metrics` — all taking an optional `period_offset`. There is **no `get_earnings_per_share()`**: read diluted EPS from the `us-gaap_EarningsPerShareDiluted` row of the income statement, or compute `net_income / shares_outstanding_diluted`.

Company facts (long history):

```python
facts = Company("GOOG").get_facts()
facts.get_revenue(); facts.get_net_income(); facts.get_total_assets()
facts.time_series("Revenues")
```

## Getting and filtering filings

```python
filings = get_filings()                       # all filings this year (market-wide)
filings = get_filings(2025, 3)                # by year/quarter
filings = get_latest_filings()                # filed just now
filings = company.get_filings(form="10-K")    # per-company
recent = filings.filter(form=["10-K","10-Q"], date="2024-01-01:")  # chain filters
f20 = filings.head(20)                        # ALWAYS limit before iterating
filing = filings.latest()
filing = get_by_accession_number("0000320193-20-34576")
```

On a Filing:

```python
filing.html() / filing.text() / filing.markdown()  # content formats (text/markdown are RAG-ready)
filing.xbrl()                                       # XBRL object or None
filing.obj() / filing.obj_type                      # typed object / preview its type
filing.attachments; filing.attachments[0].download()
filing.search("query", regex=False)                 # search within the filing
filing.filing_date; filing.period_of_report; filing.report_date  # dates (there is no filing.period)
```

A `Filings` result is directly iterable (`for f in filings.head(4): ...`) — there is no `.to_list()`. Use `.to_pandas()` or `.to_dict()` for tabular access.

Form types: use strings like `"10-K"`, `"10-Q"`, `"8-K"`, `"13F-HR"`, `"4"`, `"DEF 14A"`, `"NPORT-P"`. The `edgar.enums.FormType` enum (e.g. `FormType.ANNUAL_REPORT`) also works.

## Filing-type quick reference

**10-K / 10-Q** — `company.latest("10-K")` → `.obj()` → `tenk['Item 1A']` (risk factors), `tenk.business_description`, `tenk.risk_factors`, `tenk.mda`, `tenk.auditor` (name, firm_id), `tenk.subsidiaries`. Item keys are like `"Item 1A"`; not every filing has every item — check before using.

**8-K** — items have dots: `eightk['Item 2.02']` or `eightk['2.02']`. Common items: 1.01 material agreements, 2.02 earnings, 5.02 officer/director changes, 7.01/8.01 other events, 9.01 exhibits. Earnings 8-Ks: `eight_k.has_press_release` → `eight_k.press_releases[0].text()`; `eight_k.has_earnings` → `eight_k.get_income_statement()` etc. (safe accessors return empty DataFrames when missing). Check `income.scale` / use `scaled_dataframe` — press-release tables are often "in millions". Quirks: some 8-K/8-K/A fail `.obj()` with 'NoneType' download errors → fall back to `filing.markdown()` or raw Archives fetch; `press_releases` is a collection (no `.text()`) → use `.press_releases[0].text()`; `get_income_statement()` works even when press-release parsing fails.

**Proxy DEF 14A** — `proxy.peo_name`, `proxy.peo_total_comp`, `proxy.executive_compensation` (5yr DataFrame), `proxy.pay_vs_performance`.

Details in [references/filings.md](references/filings.md).

## Insider trades (Form 4)

```python
form4 = Company("TSLA").get_filings(form="4").latest().obj()
summary = form4.get_ownership_summary()   # ONE object, not a list — do not iterate it
summary.primary_activity                  # "Purchase" | "Sale" | "Mixed" | "Option Exercise" | ...
summary.net_change                        # + = bought, - = sold
summary.net_value; summary.insider_name; summary.has_10b5_1_plan
form4.market_trades                       # DataFrame: Date, Shares, Price, Code, AcquiredDisposed
form4.common_stock_purchases / common_stock_sales / option_exercises / derivative_trades
```

`market_trades`, `common_stock_purchases`, `common_stock_sales` overlap — the common-stock properties are subsets of `market_trades`. For trade-level analysis use ONE of them (or filter `market_trades` by `Code`); combining them double-counts rows.

Loop multiple filings: `for f in company.get_filings(form="4").head(20): f.obj().get_ownership_summary()`

Per-insider aggregation over many filings — concat the per-filing summary rows, no manual dicts:

```python
import pandas as pd
df = pd.concat([f.obj().to_dataframe(detailed=False)
                for f in company.get_filings(form="4").head(20) if f.obj()],
               ignore_index=True)
by_insider = df.groupby('Insider')[['Net Change', 'Net Value']].sum()
```

Transaction codes: P=open market purchase, S=open market sale, A=grant/award, M=option exercise, F=tax withholding (A/M/F are not real buys/sells).

## **Multi-fund 13F pulls:** `Company(cik).get_filings(form="13F-HR").head(1).obj()` takes ~2-5s per fund — 12 funds blows a 30s tool timeout. Write a script, run with `nohup ... &`, sleep+poll the log. Mega-managers file under SUCCESSOR CIKs after reorganizations: BlackRock's 1364742 stopped at 2024-06-30; CIK 2012383 files from 2026. Vanguard 102909 stopped after 2025-12-31 in this env. Find new CIKs via EDGAR full-text search `https://efts.sec.gov/LATEST/search-index?q="NAME"&forms=13F-HR&startdt=..&enddt=..` (browse-edgar atom endpoint is flaky/timeouts). State Street (93759) returns "no 13F-HR" via edgartools — resolve manually if needed.

```python
thirteenf = Company(1423053).get_filings(form="13F-HR").latest().obj()   # Citadel
h = thirteenf.holdings            # DataFrame: Issuer, Ticker, Value, SharesPrnAmount, Cusip, PutCall
thirteenf.compare_holdings()      # NEW / CLOSED / INCREASED / DECREASED vs prior quarter
thirteenf.holding_history(periods=4)
```

Gotchas: in edgartools 5.56 the parsed 13F `.holdings` `Value` came back in **dollars, not $1,000s** (Berkshire 227.9M AAPL sh × ~$289 = raw 65,950,296,923) — sanity-check share×price against Value before scaling; prefer `Cusip` over `Ticker` for lookups (filter `Cusip.startswith('037833100')` for Apple Inc. — Issuer contains('APPLE') also matches Apple Hospitality REIT); 13F data lags quarter-end by up to 45 days; to find holders of a stock, filter by the fund filer first — never iterate all 13Fs.

## Valuation calcs (PE, TTM earnings)

SEC quarterly filings only carry this quarter, the same quarter last year, and YTD for both. To build a 4-quarter (TTM) figure:

```python
company = Company("NVDA")
q_fin = company.get_quarterly_financials()     # 10-Q data
a_fin = company.get_financials()               # 10-K data

def eps(df, concept, col):
    row = df[df['concept'] == concept]
    v = row.loc[:, col].iat[0]
    return float(v) if v is not None else None

qcols = [c for c in q_fin.income_statement().to_dataframe().columns
         if 'Q)' in c or 'YTD' in c]           # period-label columns
qd = q_fin.income_statement().to_dataframe()
ad = a_fin.income_statement().to_dataframe()
acols = [c for c in ad.columns if '(FY)' in c]

ttm_eps = (eps(ad, 'us-gaap_EarningsPerShareDiluted', acols[1])   # prior FY
           - eps(qd, 'us-gaap_EarningsPerShareDiluted', ytd_prev)  # prior-year split YTD
           + eps(qd, 'us-gaap_EarningsPerShareDiluted', ytd_cur))  # current YTD

pe = market_price / ttm_eps                    # price comes from outside SEC data
```

SEC EDGAR has **no stock price** — for multiples you need price/market-cap from a market-data source, then divide by TTM EPS. Do not use the prior fiscal year's EPS as the TTM denominator: it goes stale the moment a new quarter is filed. Prefer per-share values (EPS) directly over net_income/shares because share counts and one-offs differ.

## XBRL deep dive

Only needed for segments, footnotes, or custom concepts — see [references/xbrl.md](references/xbrl.md).

## Common pitfalls (memorize these)

1. **Always limit before iterating filings** — `company.get_filings()` fetches thousands. Use `.head(n)` (not `list(x)[:n]`) or `.latest()`.
2. **Financial values are raw integers in dollars** — format with `f"${revenue/1e9:.1f}B"`. Exceptions: 13F `Value` is in $1,000s; 8-K press-release tables may be in millions (check `.scale`).
3. **Quick getters can return None** (`get_revenue()`, `filing.xbrl()`) — guard before math.
4. **`get_ownership_summary()` returns one object** — iterate filings, not the summary.
5. **DataFrames**: statement → `.to_dataframe()`; filings list → `.to_pandas()`.
6. **Invalid form strings** raise ValueError with suggestions — e.g. `"10k"` should be `"10-K"`.

## When things go wrong

- `EDGAR_IDENTITY` missing → SEC blocks requests; set it first.
- 403s / rate limiting → the library is rate-limit aware, but for bulk work slow down and batch queries.
- Network required on first request; the library caches smartly afterwards.
