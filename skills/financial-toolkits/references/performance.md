# Performance — Sharpe, Sortino, CAPM, Fama-French, correlations

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/performance

Access through a `Toolkit` instance: `companies.performance.<function>()`.
Most functions accept `period="daily|weekly|monthly|quarterly|yearly"`.

## Verified calls

```python
companies.performance.get_sharpe_ratio(period="weekly")
companies.performance.get_sortino_ratio()
companies.performance.get_calmar_ratio()
companies.performance.get_omega_ratio()
companies.performance.get_correlation_matrix()          # among tickers + benchmark
companies.performance.get_factor_asset_correlations(period="quarterly")
```

## Also in this module (get_<snake_case> naming)

Beta (`get_beta`), CAPM (`get_capital_asset_pricing_model`), Treynor ratio,
excess returns & excess-return Sharpe, tracking error, information ratio,
dividend yields, factor exposures (Fama-French 3/5-factor: `get_fama_french
...` — confirm exact names via docs or introspection below), rolling
variants of the ratio family.

```bash
.venv/bin/python -c "from financetoolkit.performance.performance_controller import Performance; print([m for m in dir(Performance) if m.startswith(('get_', 'collect_'))])"
```

Notes: a SPY benchmark is downloaded automatically for beta/CAPM-type metrics
(`benchmark_ticker=None` on init to disable); `growth=True` works on
performance ratios as well.
