---
name: tradedesk-dukascopy
description: This skill enables an agent to fetch new market data (forex, indices, and stocks) from dukascopy to use in backtests. Covers Dukascopy's stock ticker naming (which differs from yfinance), install prerequisites and Python version requirements, background-execution patterns for long exports, cache/backfill semantics, and recovery when the datafeed is blocked or rate-limited (jetta JSON API fallback).
license: MIT
metadata:
  author: radiusred.uk
--- 

# SKILL: tradedesk-dukascopy

## Overview

The `tradedesk-dukascopy` tool downloads raw tick data from Dukascopy's public datafeed, converts it into deterministic CSV candle files, and writes a metadata sidecar describing how the data was produced. The tool is available at [https://github.com/radiusred/tradedesk-dukascopy](https://github.com/radiusred/tradedesk-dukascopy)

## Prerequisites

Check that the tool actually exists before verifying tickers or planning exports:

```bash
command -v tradedesk-dc-export || pip install git+https://github.com/radiusred/tradedesk-dukascopy.git
```

* The tool is **not on PyPI** — `pip install tradedesk-dukascopy` fails with
  "No matching distribution"; install from the GitHub URL above.
* Requires **Python >= 3.11**. LTS images often default to 3.10 (Ubuntu 22.04 ships
  3.10 plus a `python3.12`), so pin the interpreter explicitly:
  `python3.12 -m venv ~/.venvs/tdc && ~/.venvs/tdc/bin/pip install git+...`, then
  invoke `~/.venvs/tdc/bin/tradedesk-dc-export`.

## When to Use This Skill

Use this skill when you need to:

* Download historical FX, index, or stock/ETF tick data
* Generate OHLCV candles at any timeframe (1min, 5min, 15min, 1H, 1D, etc.)
* Backfill missing data for dates that previously failed to download
* Probe an instrument to determine its price format (float vs int)
* Map a yfinance stock ticker to Dukascopy's ticker format (see Stock Market Data below)

## Basic Usage

### Export candles for a date range

```bash
tradedesk-dc-export --symbols EURUSD GBPUSD \
  --from 2025-01-01 --to 2025-01-31 \
  --resample 5min \
  --out data \
  --cache-dir /path/to/marketdata \
  --price-divisor 1000 \
  --workers 1
```

Key arguments:

| Argument          | Description                                                           |
| ----------------- | --------------------------------------------------------------------- |
| `--symbols`       | One or more symbols to export (space-separated)                       |
| `--from` / `--to` | Inclusive date range in YYYY-MM-DD format                             |
| `--resample`      | Output candle size (e.g., 5min, 15min, 1H). Omit for tick-only output |
| `--out`           | Output directory for CSV files (required if `--resample` is set)      |
| `--cache-dir`     | Persistent cache for downloaded .bi5 files and daily candles          |
| `--price-divisor` | Divisor for int32-encoded prices (see Price Scaling below)            |
| `--workers`       | Number of concurrent symbol workers (default: 4)                      |

### Run exports in the background

Exports routinely take minutes (one symbol-day on a cold cache ≈ 1–2 min; FX months
longer), so a foreground run risks being killed by a command timeout mid-download.
Start detached and poll the log instead — and keep **each poll short enough to fit the
command timeout** (`sleep 25 && grep ...`; a `sleep 60` poll dies in a 30 s harness):

```bash
nohup tradedesk-dc-export ... > export.log 2>&1 & echo "started pid $!"
# repeat every ~25 s until the summary line appears:
sleep 25; grep -E "hours total=|✓|✗|ERROR" export.log | tail -5
```

Timing expectations: a healthy one-symbol-day export ≈ 1 min; a fully blocked datafeed
fails hour-by-hour for ≈ 2 min before the final error (2 s connect timeout × 3 retries
× 24 hours ÷ threads); a cache-only re-run after a jetta backfill takes seconds — run
that one in the foreground.

Tip: before the *first* export on a new host, spend one second on the datafeed probe
from *When the datafeed is blocked* below — `000`/`503` means skip the doomed run and
start with the jetta backfill instead.

### Probe mode (detect price format)

```bash
tradedesk-dc-export --symbols GBPSEK \
  --from 2025-07-01 --to 2025-07-01 \
  --probe
```

Probe mode downloads one hour and prints sample ticks at various divisors without writing output files.

## Price Scaling (`--price-divisor`)

Dukascopy stores tick prices differently per instrument:

| Instrument Type           | Format  | Typical Divisor |
| ------------------------- | ------- | --------------- |
| Major FX (EURUSD, GBPUSD) | int32   | 1000            |
| JPY crosses (USDJPY)      | int32   | 100000          |
| Indices (USA500)          | float32 | 1 or 10         |
| Stocks/ETFs (AAPL.US/USD) | int32   | 1000            |

If you see prices like `1.097675` instead of `1.09767`, you're using the wrong divisor.

## Downloading Stock Market Data

Dukascopy also serves tick data for roughly a thousand stocks and ETFs across
US and European exchanges — but **Dukascopy tickers are not yfinance tickers**. The
datafeed uses Dukascopy's own `TICKER.EXCHANGE/CURRENCY` naming, so a plain
yfinance-style symbol (`AAPL`, `VOD.L`) downloads nothing.

### Ticker format

Pass the Dukascopy name directly as `--symbols` input; the tool strips the
separators and uppercases it into the datafeed folder name, the cache
directory, and the output filenames:

```
AAPL.US/USD  ->  datafeed folder AAPLUSUSD  ->  AAPLUSUSD_5MIN_bid.csv
```

### yfinance → Dukascopy mapping

| Exchange           | yfinance    | Dukascopy (`--symbols`) | Notes                          |
| ------------------ | ----------- | ----------------------- | ------------------------------ |
| US (NYSE/NASDAQ)   | `AAPL`      | `AAPL.US/USD`           | `GOOG.US/USD` = Alphabet C     |
| US ETFs            | `SPY`       | `SPY.US/USD`            |                                |
| London             | `VOD.L`     | `VOD.GB/GBX`            | `.GB`, quoted in pence (GBX)   |
| Xetra (Frankfurt)  | `SIE.DE`    | `SIE.DE/EUR`            |                                |
| Euronext Paris     | `MC.PA`     | `MC.FR/EUR`             |                                |
| Euronext Amsterdam | `ASML.AS`   | `ASML.NL/EUR`           |                                |
| Borsa Italiana     | `ENI.MI`    | `ENI.IT/EUR`            |                                |
| Madrid             | `SAN.MC`    | `SAN.ES/EUR`            |                                |
| SIX Swiss          | `NESN.SW`   | `NESN.CH/CHF`           |                                |
| Stockholm          | `ERIC-B.ST` | `ERICB.SE/SEK`          | share-class dash removed       |
| Helsinki           | `ELISA.HE`  | `ELI1V.FI/EUR`          | code itself differs            |
| Copenhagen         | `CARL-B.CO` | `CARLB.DK/DKK`          | share-class dash removed       |
| Oslo               | `ORK.OL`    | `ORK.NO/NOK`            |                                |
| Brussels           | `ABI.BR`    | `ABI.BE/EUR`            |                                |
| Mexico             | `AMXL.MX`   | `AMXL.MX/MXN`           | same ticker                    |

Conversion rules from a yfinance ticker:

* US: append `.US/USD`.
* Swap the exchange suffix: `.L`→`.GB`, `.PA`→`.FR`, `.AS`→`.NL`, `.MI`→`.IT`,
  `.MC`→`.ES`, `.SW`→`.CH`, `.ST`→`.SE`, `.HE`→`.FI`, `.CO`→`.DK`, `.OL`→`.NO`,
  `.BR`→`.BE`.
* Remove share-class dashes (`ERIC-B` → `ERICB`).
* Append the quote currency: `USD` (US), `EUR` (eurozone), `GBX` (London
  shares, pence), or `CHF`/`SEK`/`DKK`/`NOK`/`MXN` as appropriate.
* Some tickers differ entirely (e.g. Finnish stocks use local codes:
  `ELISA.HE` → `ELI1V.FI/EUR`), and a few London ETFs quote in `GBP` (pounds)
  instead of `GBX` (pence) — always verify before exporting (the Yahoo chart API
  under *Verify a ticker* is a good reference source).

**Unit trap:** London shares are quoted in GBX (pence), which matches
yfinance's GBp convention for `.L` tickers. But London ETFs quoted in GBP on
Dukascopy appear as GBp on yfinance — a 100× unit difference. Compare a
verified reference price before mixing sources.

### Verify a ticker before a long export

Before a multi-day export, confirm the code resolves using Dukascopy's JSON
endpoint. Convert the name to the API code by replacing `/` with `-`
(`AAPL.US/USD` → `AAPL.US-USD`) and note this endpoint uses a **1-based**
month. Pick an hour inside the exchange session (UTC): US 14:30–21:00, Europe
07:00–15:30 (summer times).

```bash
curl -s "https://jetta.dukascopy.com/v1/ticks/AAPL.US-USD/2025/6/2/15"
# {"timestamp":...,"ask":201.1,"bid":201.0,...}  <- valid ticker + session price
# {"error":"Unknown instrument",...}             <- wrong spelling/suffix/currency
```

The reference `ask`/`bid` values also sanity-check the currency and scale
(e.g. `VOD.GB-GBX` ≈ 76.6 pence, `SIE.DE-EUR` ≈ 211.4 euros).

Month conventions are **opposite** between the two hosts: the jetta endpoint above is
1-based (`.../2025/6/2/...` = June 2), while datafeed URLs and the on-disk cache layout
are 0-based (`.../2025/05/02/...` = June 2). Mixing them up silently targets the wrong
month.

For an independent reference price (unit traps, sanity checks), Yahoo's chart API
serves 1-min bars for recent sessions:

```bash
curl -s -A "Mozilla/5.0" \
  "https://query1.finance.yahoo.com/v8/finance/chart/NVDA?period1=<start_epoch>&period2=<end_epoch>&interval=1m"
```

Yahoo silently clamps or shifts windows that are too wide or out of range onto recent
data, which can masquerade as a successful match — always verify the returned
timestamps fall on your session date, and prefer ≤ 1-day windows (`period1` = your day
00:00 UTC, `period2` = next day 00:00 UTC).

### Price divisor for stocks

All stocks are int32-encoded with a universal point factor of 0.001, so use
`--price-divisor 1000`:

```bash
tradedesk-dc-export --symbols AAPL.US/USD \
  --from 2025-06-02 --to 2025-06-02 \
  --price-divisor 1000 --probe
```

The divisor-1000 row should print a sane dollar/euro/pence price (AAPL ≈ 201).
Volume is in shares.

### Trading-session gotchas

* Stocks only tick during exchange hours. Every stock trading day contains
  many no-data hours, so the log summary shows large `missing_404` /
  `missing_200` counts — normal for stocks, not a backfill failure.
* Closed hours count as permanent gaps, so days younger than
  `--commit-partial-after-days` (default 7) may not yet commit to the daily
  candle cache. For stock exports pass `--commit-partial-after-days 0` so
  trading days commit immediately from their in-session hours. Weekends and
  holidays still produce no candles.
* Stock tick data generally starts in early 2017 (some European names 2011–
  2016); earlier dates return nothing.

### Worked example

5-minute candles for Apple and Microsoft over one month:

```bash
tradedesk-dc-export --symbols AAPL.US/USD MSFT.US/USD \
  --from 2025-06-01 --to 2025-06-30 \
  --resample 5min \
  --out data/stocks \
  --cache-dir /path/to/marketdata \
  --price-divisor 1000 \
  --commit-partial-after-days 0 \
  --workers 2
```

Produces (note the normalised symbol in the filenames):

```
data/stocks/
  AAPLUSUSD_5MIN_bid.csv
  AAPLUSUSD_5MIN_bid.csv.meta.json
  AAPLUSUSD_5MIN_ask.csv
  AAPLUSUSD_5MIN_ask.csv.meta.json
  MSFTUSUSD_5MIN_bid.csv
  ...
```

### Do not normalise stock caches

`tradedesk-dc-normalize` corrects price scales using expected price ranges
derived from FX/index/commodity instruments. It has no stock bands, so on a
stock cache it treats a real price (AAPL ≈ 200) as over-scaled and divides it
down (~2.0), silently corrupting the data. Never run `tradedesk-dc-normalize`
on stock symbols. If a stock cache was exported with the wrong divisor, delete
the affected day files under `cache/AAPLUSUSD/` and re-export with
`--price-divisor 1000` (or use `tradedesk-dc-rescale`, which snaps to the
cache's own dominant scale and is safe for stocks).

## Re-Runs for Backfilling Missing Data

**This is the most important section for backfilling.**

### How the cache works

The tool maintains two-level caching:

1. **Hourly tick cache**: `.bi5` files downloaded from Dukascopy
2. **Daily candle cache**: 1-minute candles compressed as `.csv.zst` files

When a full day's data is successfully processed, the hourly `.bi5` files are deleted and replaced with daily 1-minute candle files. This makes subsequent exports much faster.

### Re-running is safe and efficient

Re-running the same export command is **idempotent** and is the intended way to fill gaps:

```bash
# First run - some hours failed due to Dukascopy rate limits
tradedesk-dc-export --symbols EURUSD \
  --from 2025-01-01 --to 2025-01-07 \
  --resample 5min \
  --cache-dir /path/to/marketdata \
  --price-divisor 1000

# Re-run - fills in missing hours only
tradedesk-dc-export --symbols EURUSD \
  --from 2025-01-01 --to 2025-01-07 \
  --resample 5min \
  --cache-dir /path/to/marketdata \
  --price-divisor 1000
```

On re-run, the tool:

* Skips days that already have complete daily candle cache
* Downloads only missing hourly `.bi5` files
* Retries hours that previously returned 404 or decode failures
* Completes quickly once cache is warm

> **Half-failed days become permanent under `--commit-partial-after-days 0`.**
> A re-run skips any day whose daily candle CSVs already exist, and with `0` (the
> recommended stock setting) a day commits immediately *even when some of its hours
> failed* — those hours are then never retried and the gaps are baked in (recorded in
> `cache/<SYMBOL>/_partial_days.jsonl`). Only days with no candle files yet (e.g. every
> hour failed) are retried in full.
>
> To refill a half-failed day, delete that day's candle files
> (`cache/<SYMBOL>/<YYYY>/<MM-1>/<DD>_bid.csv.zst` and `_ask.csv.zst`; 0-based month)
> and re-run once the datafeed is healthy — or backfill the missing hours from jetta
> first (see *When the datafeed is blocked*).

### Why hours might be missing

* **HTTP 404**: Dukascopy has no data for that hour (weekends, holidays, illiquid hours)
* **Decode failure**: Corrupt or incomplete download, or price format mismatch
* **Network failures**: connect timeouts or HTTP 503 from an unreachable or throttled
  datafeed. The summary counts these under `missing_404` too — that counter does not
  mean a real 404. Check the WARNING lines instead:
  `grep WARNING export.log | grep -cE "timed out|503"` (non-zero ⇒ the datafeed is
  unhealthy — see *When the datafeed is blocked* below)
* **Rate limiting**: Dukascopy sometimes returns empty/partial data under load

All of these are retried on re-run **only for days that have not yet been committed to
the daily candle cache** — see the warning above.

### Detecting gaps

Check the log output for patterns like:

```
EURUSD: hours total=168, missing_404=12, missing_200=8, downloaded=120, decode_failed=2
```

If `missing_404` or `decode_failed` is non-zero, first determine *why* (real 404s vs
network failures — see *Why hours might be missing*), then re-run to fill the
retriable gaps.

## When the datafeed is blocked (mass timeouts / 503)

Symptom: nearly every hour logs
`WARNING skipping ... after 3 failed attempts (ConnectTimeoutError ...)` or
`(503 Server Error ...)`, and the run ends with `No data produced for symbol=...`.
Re-running cannot help until the host responds — the tool's HTTP budget is fixed
(2 s connect / 10 s read / 3 retries, not configurable via CLI).

1. Probe the datafeed directly (0-based month in the path):

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 \
     "https://datafeed.dukascopy.com/datafeed/NVDAUSUSD/2026/07/31/14h_ticks.bi5"
   ```

   `000` (connect/timeout) or `503` ⇒ blocked. `404` ⇒ genuinely no data for that
   hour. For stocks many `404`s are *normal* (closed hours) — a block shows up as
   failures on in-session hours.

2. While the datafeed is blocked, backfill the cache from Dukascopy's **jetta**
   JSON API, which usually still answers. The skill bundles a ready-made converter
   at `scripts/jetta_backfill.py`, next to this SKILL.md:

   ```bash
   python3 <skill-dir>/scripts/jetta_backfill.py --symbol NVDA.US/USD \
     --from 2026-08-31 --to 2026-08-31 --cache-dir /path/to/cache
   ```

   **Backfill the FULL date range, not just session hours** (drop `--hours`):
   jetta answers `200` with empty arrays for closed hours and the script caches those
   as 0-byte `.bi5` files — that is what stops a subsequent export from re-attempting
   every closed hour (weekends/nights) against the dead datafeed at ~10–14 s per
   failed hour. Do not rely on `days loaded from cache` in export logs to judge the
   backfill: it counts only the *daily candle* cache; freshly backfilled hourly
   `.bi5` files still show as `0 days loaded from cache` while decoding fine.

   If your harness only materializes the markdown and there is no `scripts/` directory
   on disk, read the script through your skill store (it ships as
   `scripts/jetta_backfill.py` alongside this file) or use the manual curl+python
   recipe in [references/troubleshooting.md](references/troubleshooting.md) §6 — it
   produces identical cache files. Don't re-derive the encoding from scratch.

   Then re-run the normal export — it decodes the injected hours from cache without
   touching the datafeed (seconds; foreground is fine).

2b. If BOTH datafeed and jetta are throttled (both return 429), use Dukascopy's
   official fallback: the Requester-Pays S3 bucket `cfg-public-proper-wallaby`
   (eu-west-1; needs AWS CLI + credentials). Daily tick files, verified working
   for US stocks when the HTTP hosts 429:

   ```
   aws s3 ls s3://cfg-public-proper-wallaby/ --region eu-west-1 --request-payer requester   # instruments (TICKER+EXCH+CUR, e.g. NVDAUSUSD)
   aws s3 ls s3://cfg-public-proper-wallaby/NVDAUSUSD/2026/08/ --region eu-west-1 --request-payer requester  # month is 0-BASED: 08 = September
   aws s3 cp s3://cfg-public-proper-wallaby/NVDAUSUSD/2026/08/14_ticks.bi5 . --region eu-west-1 --request-payer requester
   ```

   One file per DAY (not hour): `<DD>_ticks.bi5`, LZMA, 20-byte big-endian
   records `>IIIff` = ms-since-DAY-start UTC (uint32), ask_int, bid_int,
   ask_volume, bid_volume. Scale by the usual price divisor (stocks 1000).
   Missing day file = no ticks that day. Volume units here are raw float32
   (~0.5/min for a US stock) — they do NOT match the datafeed route's share
   counts; do not mix volume across routes (close prices are identical).
   To reproduce tradedesk-dc-export output: aggregate ticks to 1-min bid
   candles grouped by `floor(ts,1min)+1min` (bar labelled by next minute,
   first US bar 13:31, last 20:00 -> 390 bars/day). Cost ~$0.06/pair, a
   week of one stock is ~1 MB. Wiki: dukascopy.com/wiki/en/development/data-export/

   The bundled `scripts/jetta_backfill.py` also accepts `--sleep N` to pace
   requests and backs off on 429 instead of failing fast.

3. Endpoint reference, the verified tick-array encoding, a manual curl+python recipe,
   and validation steps: [references/troubleshooting.md](references/troubleshooting.md).

## Output Files

When `--resample` is specified, the tool produces:

```
out/
  EURUSD_5MIN_bid.csv
  EURUSD_5MIN_bid.csv.meta.json
  EURUSD_5MIN_ask.csv
  EURUSD_5MIN_ask.csv.meta.json
```

The `.meta.json` sidecar contains the exact parameters used, making datasets reproducible.

## Common Patterns

### Parallel export of multiple symbols

```bash
tradedesk-dc-export --symbols EURUSD GBPUSD USDJPY \
  --from 2025-01-01 --to 2025-12-31 \
  --resample 1H \
  --out /data/2025 \
  --cache-dir /data/cache \
  --price-divisor 1000 \
  --workers 2
```

### Build up cache incrementally

```bash
# Month 1
tradedesk-dc-export --symbols EURUSD --from 2025-01-01 --to 2025-01-31 --cache-dir /data/cache --price-divisor 1000

# Month 2 - re-runs are instant for cached days
tradedesk-dc-export --symbols EURUSD --from 2025-02-01 --to 2025-02-28 --cache-dir /data/cache --price-divisor 1000
```

## CLI Reference

```
tradedesk-dc-export --help

  --symbols SYMBOL [SYMBOL ...]  One or more symbols to export
  --from YYYY-MM-DD              Inclusive start date
  --to YYYY-MM-DD                Inclusive end date
  --resample RULE                Candle size (e.g., 5min, 1H, 1D)
  --price-divisor FLOAT          Divisor for int32 prices (default: 1.0)
  --cache-dir PATH               Cache directory for .bi5 and daily candles
  --no-cache                     Disable caching, always re-download
  --workers N                    Max parallel symbol workers (default: 4)
  --probe                        Probe mode - print ticks, no output
  --probe-ticks N                Number of ticks to show in probe mode (default: 10)
  --out PATH                     Output directory for CSV files
  --log-level LEVEL              Log level: fatal, error, warn, info, debug, trace
```