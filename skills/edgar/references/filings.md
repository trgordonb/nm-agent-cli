# Filing-type deep dive (10-K/10-Q, 8-K, Form 3/4/5, 13F, proxies)

Read this when working with a specific filing type beyond the basics in SKILL.md.

## 10-K / 10-Q data objects

```python
tenk = Company("AAPL").latest("10-K").obj()

tenk.business_description      # Item 1 text
tenk.risk_factors              # Item 1A — check truthiness, not all filings have every item
tenk.mda                       # Management Discussion & Analysis (Item 7)
tenk['Item 1A']                # section access by item key
tenk.auditor                   # .name, .firm_id (PCAOB), location
tenk.subsidiaries              # from Exhibit 21; .to_dataframe()
tenk.reports                   # report pages from FilingSummary.xml
tenk.financials.income_statement()  # same as company.get_financials()
```

Item keys for 10-K/10-Q look like `"Item 1"`, `"Item 1A"`, `"Item 7"`.

## 8-K current reports

```python
eight_k = Company("AAPL").get_filings(form="8-K").latest().obj()
eight_k.items                      # e.g. ['Item 2.02', 'Item 9.01']
eight_k['2.02']                    # works with or without "Item" prefix
```

Common items: 1.01 material agreements · 2.02 earnings · 2.03 financial obligations · 5.02 officer/director changes · 7.01 Reg FD · 8.01 other events · 9.01 exhibits.

### Press releases

```python
if eight_k.has_press_release:
    pr = eight_k.press_releases[0]
    pr.text() / pr.html() / pr.to_markdown() / pr.open()
```

### Earnings (Item 2.02 + EX-99.1)

Earnings numbers appear in 8-Ks weeks before the 10-Q. EdgarTools parses the tables automatically:

```python
if eight_k.has_earnings:
    eight_k.get_income_statement()      # safe accessor: DataFrame, empty if missing
    eight_k.get_balance_sheet()
    eight_k.get_cash_flow_statement()
    income = eight_k.income_statement   # FinancialTable or None
    income.dataframe / income.scaled_dataframe / income.scale  # scale: UNITS/THOUSANDS/MILLIONS/BILLIONS
    income.to_json() / income.to_html()
    eight_k.earnings.financial_tables   # all parsed tables
    eight_k.earnings.guidance           # forward guidance table, if any
```

Notes: `has_earnings` requires parseable tables in EX-99.1 — some earnings 8-Ks only have narrative. Press-release tables are often "in millions"; use `scaled_dataframe` or check `scale`. 8-K XBRL is typically metadata-only (DEI); financial data lives in HTML tables.

## Insider trades (Form 3/4/5)

### Form 4 — transaction summaries

```python
summary = form4.get_ownership_summary()
summary.insider_name / summary.position
summary.primary_activity      # Purchase | Sale | Tax Withholding | Grant/Award | Option Exercise | Mixed
summary.net_change            # + shares = bought, − = sold
summary.net_value             # net dollars
summary.remaining_shares
summary.has_10b5_1_plan       # True=automated plan (less signal), False=discretionary, None=no footnotes
```

Transaction detail properties on the Form4 object: `market_trades` (DataFrame: Date, Security, Shares, Price, Remaining, AcquiredDisposed ("A"/"D"), Code), `common_stock_purchases`, `common_stock_sales`, `shares_traded`, `option_exercises`, `derivative_trades` (includes exercise price/expiration).

Exports: `form4.to_dataframe()` (one row per transaction), `form4.to_dataframe(detailed=False)` (one row per filing with Net Change/Net Value/Primary Activity), `to_dataframe(include_metadata=False)`.

Metadata: `form4.form`, `reporting_period`, `insider_name`, `position`, `issuer.name`, `issuer.ticker`, `issuer.cik`, `remarks`.

### Form 3 — initial ownership

```python
form3 = Company("HROW").get_filings(form=3).latest().obj()
summary = form3.get_ownership_summary()    # InitialOwnershipSummary
summary.total_shares; summary.has_derivatives; summary.holdings
```

Each `SecurityHolding` has `security_title`, `shares`, `direct_ownership`, `ownership_description`, `is_derivative`, `exercise_price`, `expiration_date`.

### Analysis patterns

```python
# Large discretionary buys market-wide
for f in get_filings(form=4)[:20]:
    form4 = f.obj()
    if form4 and form4.get_ownership_summary().net_change > 10000:
        s = form4.get_ownership_summary()
        print(f"{s.insider_name} bought {s.net_change:,} shares of {s.issuer}")

# Dataset across many filings
import pandas as pd
df = pd.concat([f.obj().to_dataframe(detailed=False)
                for f in Company("AAPL").get_filings(form=4)[:50]
                if f.obj()], ignore_index=True)
```

## 13F institutional holdings

```python
report = Company("BRK.A").get_filings(form="13F-HR").latest().obj()
report.management_company_name; report.total_value; report.total_holdings
h = report.holdings            # aggregated by CUSIP — use for portfolio analysis
report.infotable               # per-manager rows (multi-manager filings)
report.has_infotable()         # False for 13F-NT notices (nothing held)
```

Holdings columns: `Issuer`, `Ticker` (resolved from CUSIP; may be blank), `Value` (**$1,000s**), `SharesPrnAmount`, `Type` (Shares/Principal), `Cusip`, `PutCall`.

```python
h['Value'].sum() * 1000                    # portfolio total in dollars
h[h['Cusip'] == '037833100']                # reliable lookup (prefer Cusip over Ticker)
cmp = report.compare_holdings(); df = cmp.data   # Status: NEW/CLOSED/INCREASED/DECREASED/UNCHANGED
df[df['Status'] == 'NEW']                   # new buys
report.holding_history(periods=4)           # multi-quarter trends
```

Market-wide search: `get_filings(form="13F-HR", 2024, 3)` (year, quarter positionally) or `get_filings(form="13F-HR", filing_date="2024-11-01:2024-11-15")` for date ranges. 13F `report_period` = quarter end; `filing_date` up to 45 days later. Filings back to 2005 (fixed-width TXT era) also parse.

## Proxy statements (DEF 14A)

```python
proxy = Company("AAPL").get_filings(form="DEF 14A").latest().obj()
proxy.peo_name                      # CEO name
proxy.peo_total_comp                # CEO total comp
proxy.executive_compensation        # 5-year exec comp DataFrame
proxy.pay_vs_performance            # pay vs performance DataFrame
proxy.total_shareholder_return; proxy.peer_group_tsr
proxy.proposals                     # shareholder vote items
```

## FormType enum

`from edgar.enums import FormType, PERIODIC_FORMS, PROXY_FORMS, REGISTRATION_FORMS`. Strings work everywhere — the enum just adds IDE autocomplete. Useful members: `ANNUAL_REPORT` ("10-K"), `QUARTERLY_REPORT` ("10-Q"), `CURRENT_REPORT` ("8-K"), `PROXY_STATEMENT` ("DEF 14A"), `REGISTRATION_S1` ("S-1"), etc.
