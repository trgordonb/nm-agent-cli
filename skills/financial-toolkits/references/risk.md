# Risk — VaR, CVaR, drawdowns, volatility, Hurst

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/risk

Access through a `Toolkit` instance: `companies.risk.<function>()`.
Most functions accept `period="daily|weekly|monthly|quarterly|yearly"`.

## Verified calls

```python
companies.risk.get_value_at_risk(period="weekly", distribution="historical")
# distribution: "historical" | "gaussian" | "student-t" | "cornish-fisher" | "evt"
companies.risk.get_conditional_drawdown_at_risk()
companies.risk.get_maximum_drawdown_duration()
companies.risk.get_ewma_volatility()
companies.risk.get_hurst_exponent()
```

### Maximum drawdown — `get_maximum_drawdown` gotchas (verified)

```python
companies.risk.get_maximum_drawdown(period="weekly", within_period=False)
```

- **`period="daily"` always raises** `ValueError: Intraday data is required
  for daily calculations.` — the function demands intraday historical data
  (checked against `Toolkit._historical_data["intraday"]`, which a standard
  `Toolkit(...)` never populates, regardless of plan). Use
  `period="weekly"` or `"monthly"`, or compute drawdowns manually from
  `get_historical_data()` daily closes (`1 - price/running_max`) for
  intraweek precision.
- `within_period=True` (default) gives the max drawdown *within* each period
  (e.g. worst intra-year decline per year); pass `within_period=False` for
  the single worst peak-to-trough of the whole series.
- Weekly/monthly bars smooth over intra-period extremes: a weekly-series MDD
  can read ~1–2 pp shallower than the daily one. State the basis in the
  answer.
- Default `period` follows the init: `"yearly"` unless `quarterly=True`
  (then `"quarterly"`), **not** daily — always pass `period` explicitly.

## Also in this module (get_<snake_case> naming)

Conditional VaR / Entropic VaR, maximum (and mean/`get_drawdown...`) drawdown
series, rolling volatility (`get_volatility`), Ulcer index, value-at-risk
siblings per distribution. Confirm exact names via the docs page or:

```bash
.venv/bin/python -c "from financetoolkit.risk.risk_controller import Risk; print([m for m in dir(Risk) if m.startswith(('get_', 'collect_'))])"
```

Notes: VaR-style functions return values per ticker and period; add
`standardize=True` where supported to express results as z-scores.
