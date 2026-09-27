# Economics — macro data for 60+ countries

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/economics

Two access paths:

```python
from financetoolkit import Economics             # standalone, no tickers needed
economics = Economics()                          # no FMP key required
# or, on a Toolkit instance: companies.economics.<function>()
```

Use for: CPI/inflation, GDP, unemployment, policy & market interest rates,
government debt, money supply, renewable energy, wages & pensions.

## Verified calls

```python
economics.get_consumer_price_index()             # CPI
economics.get_gross_domestic_product()           # GDP
economics.get_unemployment_rate()
economics.get_short_term_interest_rate()         # 3-month rates
economics.get_long_term_interest_rate()          # 10-year government bonds
economics.get_government_debt()
economics.get_money_supply()
economics.get_renewable_energy()
```

Most functions accept `country=` or default to all covered countries; filter
further with `frequency="quarter"|"year"` where available. Combine with
`growth=True` (e.g. YoY inflation) and `standardize=True` (SKILL.md §4).

Full dataset list (60+ series) on the docs page or:

```bash
.venv/bin/python -c "from financetoolkit.economics.economics_controller import Economics; print([m for m in dir(Economics) if m.startswith(('get_', 'collect_'))])"
```
