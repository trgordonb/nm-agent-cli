# Fixed Income — bonds, ICE BofA yields, central bank rates

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/fixed-income

Two access paths:

```python
from financetoolkit import FixedIncome          # standalone, no tickers needed
# Pass the FMP key explicitly — some calls REQUIRE it even standalone
# (e.g. get_treasury_rates raises "A FinancialModelingPrep API key is
# required" on a keyless init). Only the ICE BofA / ECB / Euribor / Fed
# rate series work without a key.
fixedincome = FixedIncome(api_key=os.environ["FINANCIAL_MODELING_PREP_API_KEY"])
# or, on a Toolkit instance: companies.fixedincome.<function>()
```

Use for: bond valuations/statistics, corporate bond yields (ICE BofA),
government bond yields, and central-bank policy rates.

## Verified calls

```python
fixedincome.get_ice_bofa_effective_yield(maturity=False)  # or "AAA"..."CCC"
fixedincome.collect_bond_statistics()
fixedincome.get_derivative_price()
fixedincome.get_government_bond_yield()          # per country
fixedincome.get_euribor_rates()
fixedincome.get_european_central_bank_rates()    # incl. deposit/LTRO rates
fixedincome.get_federal_reserve_rates()          # incl. SOFR, EFFR

# Treasury yield curve (requires the FMP key). Takes NO date arguments;
# returns a date-indexed DataFrame with STRING maturity columns:
# '1 Month', '2 Year', ... '30 Year'.
fixedincome.get_treasury_rates()
fixedincome.get_yield_curve_spread(long_maturity=10, short_maturity=2)
```

### Yield-curve spread recipe (10Y–2Y) — verified

`get_yield_curve_spread` linearly interpolates `spot_rates` with numpy, so
the Series index must be **numeric maturities in years** — passing a raw
`get_treasury_rates` row crashes with `could not convert string to float:
'1 Month'`. Convert the labels first:

```python
row = fixedincome.get_treasury_rates().iloc[-1]        # latest curve date
curve = row.set_axis([float(c.split()[0]) for c in row.index])  # '2 Year' -> 2.0
spread = fixedincome.get_yield_curve_spread(
    spot_rates=curve, long_maturity=10, short_maturity=2,
    show_input_info=False,
)
```

Full list of yield series and maturities on the docs page, or enumerate:

```bash
.venv/bin/python -c "from financetoolkit.fixedincome.fixedincome_controller import FixedIncome; print([m for m in dir(FixedIncome) if m.startswith(('get_', 'collect_'))])"
```

Notes: works well with `standardize=True` and `rolling=N` (SKILL.md §4).
