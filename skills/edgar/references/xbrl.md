# XBRL deep dive (filing.xbrl() and company.get_facts())

Only use XBRL directly when you need segments, footnotes, specific concepts, or long time series. For standard statements use `company.get_financials()` — XBRL concept names vary by company and get_financials() normalizes them.

## Facts from a single filing

```python
from edgar import Company, get_filings

filing = Company("AAPL").latest("10-K")
xb = filing.xbrl()          # XBRL object — may be None for filings without XBRL
facts = xb.facts
print(f"Total facts: {len(facts)}")

# Standard statements via xbrl
income = xb.statements.income_statement()
```

## Querying facts — chained, composable

`xb.query()` returns a `FactQuery`; chain filters and transformations:

```python
# By concept (namespace optional). Partial regex match by default:
q = xb.query().by_concept("us-gaap:Revenues")
q = xb.query().by_concept("RevenueFrom")            # matches RevenueFromContractWithCustomer...
q = xb.query().by_concept("Revenues", exact=True)   # exact match

# By human-readable label
q = xb.query().by_label("Revenue", exact=False)

# By value (lambda)
q = xb.query().by_value(lambda x: x > 1_000_000_000)
q = xb.query().by_value(lambda x: 100_000 <= x <= 1_000_000)

# By statement type
q = xb.query().by_statement_type("IncomeStatement")   # or "BalanceSheet", ...

# Full chain with transformations
df = (xb.query()
        .by_statement_type("IncomeStatement")
        .by_label("Revenue")
        .by_value(lambda x: x > 1)
        .sort_by('value', ascending=False)   # sorting
        .limit(10)                           # limiting / .offset(n) for pagination
        .to_dataframe('concept', 'label', 'value', 'period_end')  # column selection optional
     )
```

Results: `.to_dataframe(columns...)` — optionally pick columns; column info available on the query's rich display.

### Dimensions (segment/axis data)

```python
xb.facts.query().by_dimensions(...)  # facts with specific dimensions
xb.facts.query().without_dimensions()  # undimensioned facts only
```

## Company facts — multi-year history

`Company.get_facts()` aggregates XBRL facts across the whole filing history:

```python
facts = Company("GOOG").get_facts()
facts.get_revenue()               # latest annual revenue
facts.get_net_income()
facts.get_total_assets()
facts.get_shareholders_equity()
facts.get_concept("AccountsPayableCurrent")
facts.time_series("Revenues")     # time series for any concept
```

## Choosing between get_financials / get_facts / filing.xbrl

- `get_financials()` — statements with 3 periods (income) or multi-period stitching; normalized across companies; quick scalar getters (`get_revenue`, `get_net_income`, `get_operating_income`).
- `get_facts()` — 4+ years of trends for one company, any concept, via the SEC facts DB.
- `filing.xbrl()` — one filing: segments, dimensional data, footnotes, custom concepts.

Time series queries favor `get_facts()`; iterating filings to build history is the wrong tool.
