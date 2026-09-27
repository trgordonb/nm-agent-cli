# Technicals — 40+ technical indicators

Docs: https://www.jeroenbouma.com/projects/financetoolkit/docs/technicals

Access through a `Toolkit` instance: `companies.technicals.<function>()`.
Works on the historical price data (daily/weekly/monthly per `period` arg or
init). Most indicators accept window/rolling parameters.

## Categories and collect functions

```python
companies.technicals.collect_breadth_indicators()    # A/D, OBV, Chaikin, TRIN...
companies.technicals.collect_momentum_indicators()   # RSI, MACD, Stochastic, CCI...
companies.technicals.collect_overlap_indicators()    # SMA/EMA/Hull/VWAP/Bollinger...
companies.technicals.collect_volatility_indicators() # ATR, Keltner, Donchian...
```

The `collect_*` outputs double as a name index for every indicator.

## Verified calls

```python
companies.technicals.get_ichimoku_cloud()
companies.technicals.get_relative_strength_index()
```

## Indicator catalogue (each has a `get_<name>` function)

- **Breadth**: Accumulation/Distribution, Chaikin Money Flow & Oscillator,
  On-Balance Volume, Advance-Decline Ratio & Line, McClellan Oscillator &
  Summation, TRIN, Volume PVT.
- **Momentum**: RSI, MACD, Stochastic & RSI, Williams %R, Aroon, CCI, ADX,
  Ultimate Oscillator, Rate of Change, Percentage Price/Volume Oscillator.
- **Overlap**: SMA, EMA, DEMA, TRIX, WMA, Hull MA, VWAP, Parabolic SAR,
  Pivot Points, Bollinger Bands, Moving-Average Envelopes, Ichimoku Cloud.
- **Volatility**: ATR, Keltner Channels, Donchian Channels, Volatility Cone,
  Deviation/Variance/Standard Deviation, Ulcer Index, Mass Index.

Windows are configurable (e.g. `get_relative_strength_index(window=21)`);
confirm a specific indicator's signature on the docs page or via
`collect_*` output columns.

## Output shape (verified)

`collect_momentum_indicators()` (same for other categories) returns daily
rows (`PeriodIndex` "D") with **(Indicator, Ticker) as MultiIndex columns** —
including a "Benchmark" column set. Select one ticker and year with:

```python
mom = companies.technicals.collect_momentum_indicators()
tsla_2026 = mom.xs("TSLA", axis=1, level=1).loc["2026"]
```

For calendar-year indicator requests, initialize `Toolkit(start_date=...)`
roughly **one year earlier** than the requested window — indicators like RSI,
MACD and ADX need a warm-up period, otherwise their first weeks of the
requested year are invalid (NaN or biased).
