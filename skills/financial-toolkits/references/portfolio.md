# Portfolio — analyse your own positions

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/portfolio

Standalone module, loads positions from a CSV/XLSX in the exact template
format the toolkit documents (columns: Identifier, Currency, Cost,
Purchase Date, Type, Weight). A sample template ships with the repo
(`example` option).

```python
from financetoolkit import Portfolio

portfolio = Portfolio(
    # file="workspace/positions.xlsx",  # or example=True for the demo book
    example=True,
)
```

## Verified call

```python
portfolio.get_positions_overview()
```

Because positions come from your own file, the rest of the toolkit operates
on them like tickers: performance, risk and technical modules work through
the same `Toolkit(...)` interface using the portfolio's identifiers.

Template requirements and further functions are on the docs page above —
read it before constructing the positions file.
