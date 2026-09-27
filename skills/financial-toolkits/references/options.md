# Options — pricing, implied volatility, Greeks

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/options

Access through a `Toolkit` instance: `companies.options.<function>()`.
Greeks/pricing are model-based; volatility needs live option chains (requires
an FMP plan that includes options data).

## Verified calls

```python
companies.options.get_black_scholes_model()
companies.options.get_delta(expiration_time_range=180)
companies.options.get_gamma()
companies.options.get_theta()
companies.options.get_vega()
companies.options.collect_first_order_greeks()   # Delta, Gamma, Vega, Theta, Rho
companies.options.collect_second_order_greeks()
companies.options.collect_third_order_greeks()
```

Also available: binomial (Cox-Ross-Rubinstein) pricing, implied volatility,
Probability of Profit / ITM calculations — exact names on the docs page:

```bash
.venv/bin/python -c "from financetoolkit.options.options_controller import Options; print([m for m in dir(Options) if m.startswith(('get_', 'collect_'))])"
```

Notes: `expiration_time_range` is in days (e.g. `180` = expire in ~6 months);
Greeks functions accept spot price, strike, volatility, risk-free rate and
dividend-yield overrides — see docs for defaults.
