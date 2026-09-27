# Toolkit core — historical data & financial statements

Init reference (see SKILL.md §2). Docs:
https://www.jeroenbouma.com/projects/financetoolkit/docs/introduction

## Toolkit(...) parameters

| Parameter | Default | Purpose |
|---|---|---|
| `tickers` | required | list of tickers (e.g. `["AAPL", "MSFT"]`); include benchmark here too |
| `api_key` | required | FMP key from `.env` (`FINANCIAL_MODELING_PREP_API_KEY`) |
| `start_date` | today-10y | e.g. `"2020-01-01"` (free plan caps at 5 years) |
| `quarterly` | `False` | quarterly statements/ratios instead of annual |
| `enforce_source` | `None` | `"FinancialModelingPrep"` or `"YahooFinance"` to force one source |
| `benchmark_ticker` | `"SPY"` | benchmark for performance/risk; `None` disables |
| `convert_currency` | `True` | convert foreign statements to USD |
| `use_cached_data` | `False` | cache downloads to a pickle for reuse |

## Historical market data

```python
df = companies.get_historical_data(period="daily")  # daily | weekly | monthly | yearly
```

Returns per ticker: Open, High, Low, Close, Adj Close, Volume, Dividends,
Stock Splits, Return and Cumulative Return columns. Select one ticker with
`df.xs("AAPL", axis=1, level=1)`.

## Financial statements (as-reported, normalized fiscal calendar)

```python
companies.get_income_statement()        # 50+ line items
companies.get_balance_sheet_statement() # 45+ line items
companies.get_cash_flow_statement()     # 45+ line items
```

Statements follow the ticker's fiscal calendar (normalized so Apple's Jul–Sep
quarter appears as Q3 for cross-company comparison). `quarterly=True` on init
switches to quarterly data. `Toolkit.get_...` are alias wrappers around the
statement collectors.

Note: the first metric call on a `Toolkit` instance triggers a one-time
download of *all* statement types (income, balance, cashflow, treasury,
historical) — expect ~10–20 s of INFO logs on the first run, and use
`use_cached_data=True` on init so later runs skip this.

Tips: inspect `df.index` / `df.columns` before selecting (orientation varies);
print only selected columns; use `.to_csv("workspace/...")` for the full
table.

## When FMP quota is exhausted (HTTP 429)

After the daily limit the toolkit logs 429s and silently falls back to the
(possibly stale) shared cache. For raw price data, fetch directly from Yahoo
Finance instead — `yfinance` is already installed:

```python
import yfinance as yf
hist = yf.download("TSLA", start="2020-01-01", auto_adjust=True)  # OHLCV, Adj Close
```

Verify freshness the same way (`hist.index[-1]` should be the last trading
day) before computing anything on it.
