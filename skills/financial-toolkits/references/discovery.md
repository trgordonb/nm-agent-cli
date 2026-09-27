# Discovery module — screeners, lists, sector performance, news (standalone)

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/discovery

```python
from financetoolkit import Discovery          # top-level import works
discovery = Discovery(api_key=os.environ["FINANCIAL_MODELING_PREP_API_KEY"])
```

Importing `Discovery` from `financetoolkit.discovery` fails on 2.x — the
public class lives in `financetoolkit.discovery.discovery_controller`.

Use for: stock screening, ticker/company lists, sector & industry aggregates
(PE, performance), news, IPO calendars, biggest gainers/losers, splits.

## ⚠️ Stock screener is plan-restricted on FMP free plans

`get_stock_screener()` calls an FMP endpoint that the current API key's plan
does **not** include: it fails with `Restricted Endpoint: This endpoint is not
available under your current subscription...` and returns an empty frame whose
only column is `REQUEST FAILED`. **Recognize this on the first attempt and go
straight to the yfinance fallback below — do not retry the screener or burn
quota probing it.**

## Stock screener (paid plan) — exact signature

```python
discovery.get_stock_screener(
    market_cap_higher=20_000_000_000,   # absolute dollar filters
    price_higher=5,   price_lower=50,
    beta_higher=1.5,  beta_lower=2.0,
    volume_higher=..., volume_lower=...,
    dividend_higher=... dividend_lower=...,
    sector="Healthcare", industry="Biotechnology", country="United States",
    exchange="NYSE", is_etf=False,
    limit=1000,                          # capped; truncation is logged
)
```

These are fixed named parameters (2.x) — there are no arbitrary
`<field>_higher`/`<field>_lower` kwargs beyond the ones listed above.

## Screener fallback: yfinance (works on the free path, verified on yf 1.7.0)

```python
import yfinance as yf
from yfinance import EquityQuery

q = EquityQuery("and", [
    EquityQuery("gt", ["intradaymarketcap", 20e9]),
    EquityQuery("eq", ["region", "us"]),
    EquityQuery("eq", ["industry", "Biotechnology"]),
])
rows = yf.screen(q, size=100, sortField="intradaymarketcap", sortAsc=False)
```

- Available operators: `and`, `or`, `eq`, `ne`, `gt`, `lt`, `gte`, `lte`,
  `between`; inspect `EquityQuery.valid_fields` / `valid_values` for the
  exact vocabulary.
- Raw `yf.screen()` rows carry symbol / name / exchange / marketCap but
  **not** sector or industry — pull classification fields from
  `yf.Ticker(sym).info` when you need to show or verify them (this doubles
  as the domicile check below).
- **Pitfall 1 — "region" ≠ domicile**: `region=us` means *traded on US
  markets*, so OTC listings of foreign companies (argenx NL, CSL AU, UCB BE…)
  slip in. Enrich candidates with `yf.Ticker(sym).info` and filter on
  `info["country"] == "United States"` for a true country screen.
- **Pitfall 2 — duplicates**: the same issuer often has several OTC/primary
  symbols; dedupe on the company name (or ISIN) before ranking.
- **Pitfall 3 — taxonomy**: Yahoo's `industry` split differs from casual
  usage — large US "biotech-ish" names (Amgen, Gilead, Biogen) are classified
  as `Drug Manufacturers - General`, not `Biotechnology`. If the user's
  intent is "biotech sector", consider matching on `sector == "Healthcare"`
  plus industry variants, and say so in the answer.

## Other calls (verified against 2.2.0)

```python
discovery.get_stock_list()                 # all available tickers
discovery.get_sectors_performance()        # sector returns
discovery.get_industry_performance()
discovery.get_sector_pe() / get_industry_pe()
discovery.get_stock_news()                 # also: get_crypto_news, get_forex_news,
                                           # get_general_news, get_press_releases
discovery.get_biggest_gainers() / get_biggest_losers() / get_most_active_stocks()
discovery.get_ipo_calendar() / get_stock_splits_calendar()
discovery.get_etf_list() / get_index_list() / get_crypto_list() /
    get_forex_list() / get_commodity_list() / get_delisted_stocks()
discovery.get_stock_shares_float() / get_mergers_acquisitions_latest()
```

There is no `get_companies_list()` or `get_available_tickers()` in 2.x — use
`get_stock_list()`. Full method enumeration without API calls:

```bash
.venv/bin/python -c "from financetoolkit import Discovery; print([m for m in dir(Discovery) if m.startswith(('get_', 'collect_'))])"
```
