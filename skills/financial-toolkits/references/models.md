# Models — DuPont, WACC, EVA, Altman Z, Beneish M, Graham Number

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/models

Access through a `Toolkit` instance: `companies.models.<function>()`.

## Verified calls

```python
companies.models.get_dupont_analysis()
companies.models.get_extended_dupont_analysis()   # 5-step decomposition
companies.models.get_weighted_average_cost_of_capital()
companies.models.get_economic_value_added()
companies.models.get_altman_z_score()
companies.models.get_beneish_m_score()            # earnings-manipulation flags
companies.models.get_graham_number()
```

Notes:

- WACC and EVA accept overrides (e.g. `beta`, `market_risk_premium`,
  `tax_rate`) and otherwise derive inputs from statements + benchmark data.
- The Altman Z-Score variants (original, private, B-/C-class) and Beneish
  M-Score components are covered on the docs page — consult it before
  interpreting M-Score sub-indices.
- Cross-cutting parameters (`growth`, `trailing`, `lag`, `rolling`,
  `standardize`) apply here too (see SKILL.md §4).
