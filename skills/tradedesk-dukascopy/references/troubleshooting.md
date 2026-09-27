# Troubleshooting & the jetta fallback

Deep reference for failure modes that need more detail than SKILL.md. Start here when
an export produced nothing, garbled prices, or gaps that re-runs do not fill.

## Contents

1. [Triage: why did my export produce nothing?](#1-triage-why-did-my-export-produce-nothing)
2. [The jetta JSON API](#2-the-jetta-json-api)
3. [Verified jetta tick-array encoding](#3-verified-jetta-tick-array-encoding)
4. [bi5 format and cache layout](#4-bi5-format-and-cache-layout)
5. [Using scripts/jetta_backfill.py](#5-using-scriptsjetta_backfillpy)
6. [Manual backfill recipe (no script)](#6-manual-backfill-recipe-no-script)
7. [Refilling a half-failed day](#7-refilling-a-half-failed-day)
8. [Validating a backfilled export](#8-validating-a-backfilled-export)

## 1. Triage: why did my export produce nothing?

| Log signature | Meaning | Action |
| --- | --- | --- |
| `WARNING skipping ... (404 Client Error)` | No data for those hours (closed market for stocks) | Normal for stocks; re-run fills nothing more |
| `WARNING skipping ... (ConnectTimeoutError / timed out / 503)` | **The datafeed is blocked or throttled** | See below — re-running is futile until it responds |
| `missing_404=N` in the summary with network WARNINGs present | Same as above | The `missing_404` counter buckets *any* exhausted download (timeout, 503, 404) — never trust it alone |
| `decode_failed=N` | Downloaded but undecodable | Re-run; if persistent, price format is wrong — use `--probe` |
| `days_rejected_scale_sentry=N` | Decoded prices look implausible (wrong divisor) | Fix `--price-divisor` and delete the affected cached day |
| Final `✗ ... failed: No data produced` | Every hour failed | Follow the probe below, then the jetta fallback |

Probe the datafeed directly (path uses a **0-based month**):

```bash
curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 \
  "https://datafeed.dukascopy.com/datafeed/NVDAUSUSD/2026/07/31/14h_ticks.bi5"
```

* `000` (connect/timeout) or `503` ⇒ blocked/throttled. The tool will not get through:
  its HTTP budget is hardcoded (`timeout=(2.0, 10.0)`, `retries=3`, not configurable),
  so a 2 s-unreachable host fails every hour. Use the jetta fallback (§5) or wait.
* `404` ⇒ genuinely no data for that hour (check an in-session hour, e.g. 14:00–20:00
  UTC for US stocks, before concluding).
* `200` ⇒ the datafeed is healthy; a re-run should succeed.

## 2. The jetta JSON API

`jetta.dukascopy.com` serves the same tick data as the datafeed as JSON and usually
stays reachable when the datafeed is blocked.

**Ticks** — one hour per request, **1-based month** (opposite of the datafeed):

```
https://jetta.dukascopy.com/v1/ticks/{CODE}/{Y}/{M}/{D}/{H}
# CODE = ticker with '/' replaced by '-':  NVDA.US/USD -> NVDA.US-USD
```

Response (HTTP 200 even for closed hours):

```json
{"timestamp": 1788188400000, "multiplier": 0.001,
 "ask": 219.763, "bid": 219.727,
 "times": [...], "asks": [...], "bids": [...],
 "askVolumes": [...], "bidVolumes": [...]}
```

* Closed hour / weekend / holiday: `"ask": null, "bid": null, "times": []` with HTTP 200.
* Unknown instrument or out-of-range date: HTTP 404 (or an error object). Use
  `https://jetta.dukascopy.com/v1/instruments` to list all valid codes with
  `priceScale` (e.g. NVDA `priceScale: 3` ⇒ point factor 0.001).
* `multiplier` is the instrument's point factor and matches SKILL.md's divisor table:
  `--price-divisor = 1 / multiplier` (stocks 0.001 ⇒ 1000).

## 3. Verified jetta tick-array encoding

**Do not re-derive this** — it was verified end-to-end against the tool's decoder and
Yahoo 1-min reference bars (NVDA 2026-08-31, all 7 session hours, 82,896 ticks):

* `times[i]` = ms gap after the previous tick; `times[0]` = offset of the first tick
  from the top of the hour (e.g. `1,801,001` for a 13:30 UTC session open);
  `sum(times) ≈ 3,600,000`.
* `asks[i]` / `bids[i]` = **price delta vs the previous tick**, in `multiplier` units.
  The top-level `ask` / `bid` is the **first tick's price** (the anchor), and
  `asks[0] == bids[0] == 0`. Reconstruct: `price[i] = price[i-1] + asks[i]`, starting
  from `price[0] = ask / multiplier` (integer point units).
* `askVolumes` / `bidVolumes` = absolute per-tick volumes in shares (floats; stocks
  often show a constant synthetic value, e.g. 1200).
* Consistency checks that pass with this reading (all 7 hours): 0 crossed spreads;
  reconstructed hourly min/max bracket Yahoo's trade range within ~2 cents; last tick
  of hour H vs first tick of H+1 within ~2 cents.

Two natural-looking but **wrong** readings — do not spend time on them:

* "Top-level ask/bid is the *last* tick, arrays are deltas": hour boundaries jump by
  ±$1 and ranges disagree with real sessions.
* "Arrays are absolute offsets from the top-level price": prices are pinned within
  ±0.08 of the anchor all hour, wildly flat vs real data.

## 4. bi5 format and cache layout

* A `.bi5` file is LZMA-compressed (alone format) concatenated 20-byte records,
  big-endian `>i i i f f`:
  `ms-offset-in-hour (int32), ask (int32, point units), bid (int32, point units),
  ask volume (float32), bid volume (float32)`.
  Point units = price ÷ multiplier (stocks: price × 1000 — the tool decodes with
  `--price-divisor 1000`).
* The tool auto-detects int vs float encoding per file by unpacking the first record
  as float32; int32 point prices in any sane range read as subnormal floats, so
  int-encoded files are detected correctly (stocks report `format = int`).
* Hourly cache path (**0-based month**), symbol normalized to uppercase alphanumerics:

  ```
  <cache-dir>/<SYMNORM>/<YYYY>/<MM-1>/<DD>/<HH>h_ticks.bi5
  # NVDA.US/USD, 2026-08-31 15h -> cache/NVDAUSUSD/2026/07/31/15h_ticks.bi5
  ```

* A cached file short-circuits the download entirely — **including 0-byte files**,
  which mean "no ticks this hour" and are never re-fetched. This is why cache
  injection works, and also why a wrongly-empty file is permanent until deleted.
* Once a day commits to the daily candle cache, its hourly `.bi5` files are deleted
  and `cache/<SYMNORM>/<YYYY>/<MM-1>/<DD>_bid.csv.zst` + `_ask.csv.zst` appear.

## 5. Using scripts/jetta_backfill.py

```bash
python3 <skill-dir>/scripts/jetta_backfill.py \
  --symbol NVDA.US/USD --from 2026-08-31 --to 2026-08-31 \
  --cache-dir /path/to/cache [--hours 13-21] [--force]
```

* Fetches each hour from jetta, encodes bi5 (pure integer math, no float drift), and
  writes it into the tool's cache layout. Stdlib only, works on any Python ≥ 3.8.
* Empty jetta hours (HTTP 200 + empty arrays) are cached as 0-byte files — matching
  the tool's own "no data" semantics.
* Failed hours (network errors, 404s) are left **uncached** so a later run retries
  them; the script exits non-zero in that case.
* Afterwards run the normal `tradedesk-dc-export` with the same `--cache-dir`: it
  decodes the injected hours from cache, with zero datafeed access.
* Verified end-to-end (2026-08-31 NVDA): export completed in 0.6 s —
  `missing_404=0, missing_200=17, downloaded=7, decode_failed=0` — producing 390
  1-min candles matching Yahoo's session bars.

## 6. Manual backfill recipe (no script)

```bash
# 1. Fetch an hour (1-based month!)
curl -s "https://jetta.dukascopy.com/v1/ticks/NVDA.US-USD/2026/8/31/15" -o h15.json
# 2. Encode into the tool's cache (0-based month!)
python3 - <<'EOF'
import json, itertools, lzma, struct, os
d = json.load(open('h15.json'))
mult = float(d['multiplier']); n = len(d['times'])
a0, b0 = round(d['ask']/mult), round(d['bid']/mult)
ct = list(itertools.accumulate(d['times']))
ca = list(itertools.accumulate(d['asks'])); cb = list(itertools.accumulate(d['bids']))
va = (d.get('askVolumes') or [0.0]*n)[:n]; vb = (d.get('bidVolumes') or [0.0]*n)[:n]
raw = b''.join(struct.pack('>i i i f f', t, a0+a, b0+b, float(x), float(y))
               for t, a, b, x, y in zip(ct, ca, cb, va, vb))
out = 'cache/NVDAUSUSD/2026/07/31/15h_ticks.bi5'   # note 0-based month
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'wb').write(lzma.compress(raw, format=lzma.FORMAT_ALONE))
EOF
# 3. Re-run the normal export with the same --cache-dir
```

## 7. Refilling a half-failed day

With `--commit-partial-after-days 0`, a day that commits while some hours failed keeps
those gaps forever (recorded in `cache/<SYMBOL>/_partial_days.jsonl`), because re-runs
skip any day whose candle CSVs exist. To refill:

1. Delete the day's candle files:
   `cache/<SYMBOL>/<YYYY>/<MM-1>/<DD>_bid.csv.zst` and `..._ask.csv.zst`
   (0-based month).
2. Optionally remove the matching line from `cache/<SYMBOL>/_partial_days.jsonl` so
   the manifest stays truthful.
3. Re-run the export once the datafeed is healthy — or run `jetta_backfill.py` first
   to restore the missing hours from jetta (its `--hours` flag targets just the gaps).

## 8. Validating a backfilled export

1. `--probe` one in-session hour and confirm a sane price at the expected divisor
   (`tradedesk-dc-export --symbols NVDA.US/USD --from 2026-08-31 --to 2026-08-31
   --price-divisor 1000 --probe`).
2. Run the export; the summary should show `decode_failed=0`,
   `days_rejected_scale_sentry=0`, and `downloaded=0` (everything served from cache).
3. Cross-check against Yahoo 1-min bars (recipe in SKILL.md, *Verify a ticker*):
   request a ≤ 1-day window — Yahoo silently clamps/shifts out-of-range windows onto
   recent data, so verify the returned timestamps are your session date. Session bar
   count should match (US regular session = 390 bars), and bid closes should sit
   within a few cents of Yahoo's trade closes.
