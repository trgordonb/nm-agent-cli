---
name: financial-toolkits
description: Use the open-source FinanceToolkit (github.com/JerBouma/FinanceToolkit) locally in Python for financial analysis — 200+ ratios, indicators, models and economic indicators backed by FinancialModelingPrep (auto-fallback to Yahoo Finance). Use whenever the user asks for financial statements, ratios, valuation, performance/risk metrics, technical indicators, options & Greeks, fixed income, macro/economic data, stock screeners or financial news. This replaces the remote FinanceToolkit MCP server.
---

# FinanceToolkit (local, replaces the remote MCP server)

The FinanceToolkit is an open-source Python library that computes 200+ financial
ratios, indicators, performance/risk measurements and models with transparent,
documented formulas. Data comes from FinancialModelingPrep (FMP) with an
automatic fallback to Yahoo Finance when FMP fails or the plan does not cover
the request.

Run all Python through the project venv (`.venv/bin/python` or `uv run python`),
via the `execute` tool. Write longer scripts to `workspace/` and execute them.
The `execute` tool may not start in the project root — if `.venv/bin/python`
is not found, `cd` to the project root (or use its absolute path) and rerun.

## 1. Setup (one-time per environment)

Install into the project environment:

```bash
uv pip install financetoolkit -U
# or add it as a project dependency: uv add financetoolkit
```

Verify the install and that the API key is available:

```bash
.venv/bin/python -c "import financetoolkit; from importlib.metadata import version; print(version('financetoolkit'))"
.venv/bin/python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(bool(os.getenv('FINANCIAL_MODELING_PREP_API_KEY')))"
```

The FMP API key is already configured in the repo's `.env` as
`FINANCIAL_MODELING_PREP_API_KEY`. Always load it with `python-dotenv`; never
hard-code it.

## 2. Canonical quickstart

```python
import os
from dotenv import load_dotenv
from financetoolkit import Toolkit

load_dotenv(".env")  # explicit path — bare load_dotenv() crashes with an
                     # AssertionError (find_dotenv frame inspection) when the
                     # script is run via `python -c` or piped stdin

# Initialize ONCE with every ticker you need (data fetch is threaded,
# so one init with N tickers is much faster than N inits with one ticker).
companies = Toolkit(
    tickers=["AAPL", "MSFT"],
    api_key=os.environ["FINANCIAL_MODELING_PREP_API_KEY"],
    start_date="2020-01-01",   # limit history (FMP free plan = 5 years max)
    use_cached_data=True,      # pickle downloads so script re-runs don't re-fetch
)

# Every metric is a plain method call, e.g.:
print(companies.ratios.get_return_on_equity())
print(companies.technicals.get_relative_strength_index())
```

Standalone modules (no tickers required): `Discovery`, `Economics`,
`FixedIncome`, `Portfolio` — e.g. `from financetoolkit import Discovery`.

## 3. Module map — which reference to load

Before using a module for the first time in a session, **Read the matching
reference file**. How to reach the files depends on how this skill was loaded:

- **Local repo**: same directory as this SKILL.md, `references/` subfolder —
  use `read_file` / `glob`.
- **Via OpenViking** (`viking://.../skills/financial-toolkits`): that URI is a
  **directory**, not a readable file — `viking_read` on it fails. Call
  `viking_browse` on the directory to list children, then `viking_read` each
  file with **exactly one URI per call** (passing a list of URIs in one call
  is rejected as an invalid URI).

Each reference lists the exact calls, key parameters and a docs link.

| Task | Module | Reference |
|---|---|---|
| Find/verify tickers, screen stocks, sector performance, news | `Discovery` (standalone) | `references/discovery.md` |
| Historical OHLCV, income / balance / cash-flow statements | `Toolkit` core | `references/core.md` |
| 80+ ratios: efficiency, liquidity, profitability, solvency, valuation | `companies.ratios` | `references/ratios.md` |
| DuPont, WACC, EVA, Altman Z-Score, Beneish M-Score, Graham Number | `companies.models` | `references/models.md` |
| Sharpe, Sortino, Calmar, Omega, Beta, CAPM, Fama-French | `companies.performance` | `references/performance.md` |
| VaR, CVaR, drawdowns, EWMA volatility, Hurst exponent | `companies.risk` | `references/risk.md` |
| 40+ technical indicators: RSI, MACD, Bollinger, VWAP, ATR… | `companies.technicals` | `references/technicals.md` |
| Black-Scholes, binomial pricing, implied vol, Greeks | `companies.options` | `references/options.md` |
| Bond valuations, ICE BofA yields, ECB/Fed/Euribor rates | `companies.fixedincome` or `FixedIncome` | `references/fixedincome.md` |
| CPI, GDP, unemployment, interest rates for 60+ countries | `companies.economics` or `Economics` | `references/economics.md` |
| Analyse your own portfolio from a CSV/XLSX | `Portfolio` (standalone) | `references/portfolio.md` |

Full parameter-level documentation lives at
https://www.jeroenbouma.com/projects/financetoolkit/docs (per-module pages are
linked inside each reference file). Fetch pages with `web_to_markdown_tool`
when a needed signature is not covered locally.

## 4. Cross-cutting parameters (work on most `get_` / `collect_` calls)

- `period`: `"daily"`, `"weekly"`, `"monthly"`, `"quarterly"`, `"yearly"` —
  market-data period for performance/risk/technicals functions.
- `quarterly`: set `quarterly=True` on `Toolkit(...)` for quarterly statements
  and ratios instead of annual.
- `trailing`: trailing sum/average over N periods, e.g. `trailing=4` on
  quarterly data = TTM. Combine with `growth=True` for TTM growth.
- `growth=True` (+ `lag`, default 1): return period-over-period growth instead
  of raw values; `lag=4` on quarterly data = year-over-year.
- `rolling=N`: sliding-window value per date instead of one value per period.
- `standardize=True`: convert values into z-scores versus the metric's own
  history (Economics, Ratios, Technicals, Risk, Performance, Models, Options,
  Fixed Income).

## 5. Handling results

- Almost everything returns a `pandas.DataFrame`, but **orientation varies by
  call — always print `df.index` and `df.columns` (or `df.index.names`,
  `df.index.nlevels`) before selecting anything**. Known shapes:
  - `collect_*_ratios()` / most model calls: metrics as **rows** (Title Case
    names like "Cash Conversion Cycle"), fiscal periods as columns as a
    `PeriodIndex` (e.g. `Y-DEC` annual years). With multiple tickers the
    ticker appears as an extra index level; with a single ticker there is no
    ticker level at all (a `.loc["NVDA"]` will KeyError).
  - `get_historical_data()` and technical/performance indicator frames:
    tickers (or "Benchmark") as a **column level** —
    `df.xs('AAPL', axis=1, level=1)`; dates as a daily `PeriodIndex` rows,
    so a calendar year is a plain date slice: `df.loc["2026"]`.
- "Most recent fiscal year" = the **last column**: `df.columns[-1]` (a
  `Period`), selected via `df.iloc[:, -1]`; the prior one is
  `df.iloc[:, -2]`.
- Tables can be very large. Always select and trim before printing
  (`.loc`, `.tail(10)`, specific columns) and save full results to
  `workspace/<name>.csv` with `.to_csv()` when the user wants the data.
- The toolkit logs INFO progress lines to stderr. Silence them at the top of
  scripts: `import logging; logging.getLogger("financetoolkit").setLevel(logging.WARNING)`.

## 6. Limits & gotchas

- FMP **free** plan: 250 requests/day, 5 years of history, US-listed companies
  only. Batch tickers in one `Toolkit(...)` call to use quota efficiently.
- Installing pulls heavy deps and may upgrade packages the rest of the project
  shares (observed: `websockets` 15→17, adds `yfinance`). Prefer
  `uv add financetoolkit` so the resolution is recorded in `pyproject.toml`,
  and check `uv pip install` output for unexpected upgrades.
- Iterating on a script: keep `use_cached_data=True` on `Toolkit(...)` so
  re-runs load the pickle instead of re-downloading every statement.
- **Stale-cache trap**: the cache is a shared SQLite DB
  (`~/.config/financetoolkit/financetoolkit_cache.db`, override with
  `FINANCE_TOOLKIT_CACHE_DB`) that can serve series missing the most recent
  months — especially after the daily quota is exhausted (HTTP 429), when the
  toolkit silently falls back to whatever the cache holds. **Always print the
  fetched data range and compare its end date to today**; if it's stale,
  refetch with `use_cached_data=False`, or delete the cache DB. Don't
  reverse-engineer the cache — just bypass it.
- Foreign-company statements are converted to USD using period-end FX rates
  (disable with `convert_currency=False`); use the ticker of the home exchange
  when possible.
- A `SPY` benchmark is fetched automatically for performance/risk metrics;
  disable with `benchmark_ticker=None`.
- Fiscal quarters are normalized to calendar periods for cross-company
  comparison (Apple's Jul–Sep quarter is reported as calendar Q3).
- If a call fails due to plan restrictions, the toolkit silently falls back to
  Yahoo Finance; pass `enforce_source="FinancialModelingPrep"` on `Toolkit()`
  to surface errors instead.

## 7. Finding a call that is not in the references

1. Check the module's docs page linked in its reference file.
2. Enumerate methods locally without spending API quota:

```bash
.venv/bin/python -c "import financetoolkit, pkgutil; print(sorted(m.name for m in pkgutil.iter_modules(financetoolkit.__path__)))"
.venv/bin/python -c "from financetoolkit.ratios.ratios_controller import Ratios; print([m for m in dir(Ratios) if m.startswith(('get_', 'collect_'))])"
```

Public classes live in `financetoolkit.<module>.<module>_controller`
(`Ratios`, `Performance`, `Risk`, `Options`, `FixedIncome`, `Economics`,
`Discovery`); only `Toolkit`, `Discovery`, `Economics`, `FixedIncome` and
`Portfolio` import from the top level. `dir()` on the top-level class or on
the Toolkit instance attribute works the same way.

3. Or read the installed source under
   `.venv/lib/python3.11/site-packages/financetoolkit/` — every function is
   documented with its formula and parameters.
