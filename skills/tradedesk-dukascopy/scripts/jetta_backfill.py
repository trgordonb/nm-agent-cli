#!/usr/bin/env python3
"""Backfill tradedesk-dukascopy's hourly .bi5 cache from Dukascopy's jetta JSON API.

Use when datafeed.dukascopy.com is blocked or throttled (mass ConnectTimeout/503
warnings, "No data produced") but jetta.dukascopy.com still answers. Hours are
written into the tool's own cache layout, so a normal `tradedesk-dc-export`
re-run afterwards decodes and resamples them offline, with no datafeed access.

Verified jetta array encoding (see ../references/troubleshooting.md):
  - top-level ask/bid    = FIRST tick's price (the anchor); asks[0] == bids[0] == 0
  - asks[i], bids[i]     = price delta vs the previous tick, in `multiplier` units
  - times[i]             = ms gap after the previous tick; times[0] = offset of the
                           first tick from the top of the hour
  - askVolumes/bidVolumes = absolute per-tick volumes (floats, shares)
  - closed hours / weekends = HTTP 200 with ask=null and empty arrays
Stored bi5 record: 20 bytes, big-endian ">i i i f f" =
  ms-offset, ask_int, bid_int, ask_volume, bid_volume (prices in 1/multiplier units)
LZMA-compressed (alone format), written to:
  <cache-dir>/<SYMNORM>/<YYYY>/<MM 0-based>/<DD>/<HH>h_ticks.bi5

Example:
  python3 jetta_backfill.py --symbol NVDA.US/USD \
      --from 2026-08-31 --to 2026-08-31 --cache-dir ~/marketdata/cache
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import lzma
import os
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UTC = dt.timezone.utc
JETTA_URL = "https://jetta.dukascopy.com/v1/ticks/{code}/{y}/{m}/{d}/{h}"
RECORD = struct.Struct(">i i i f f")  # ms, ask_int, bid_int, ask_vol, bid_vol


def symbol_norm(s: str) -> str:
    """Mirror the tool's _symbol_normalise: uppercase alnum only (NVDA.US/USD -> NVDAUSUSD)."""
    cleaned = "".join(ch for ch in s.strip() if ch.isalnum())
    if not cleaned:
        raise ValueError(f"Empty symbol: {s!r}")
    return cleaned.upper()


def parse_hours(spec: str | None) -> set[int]:
    if not spec:
        return set()
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        elif part:
            out.add(int(part))
    bad = out - set(range(24))
    if bad:
        raise ValueError(f"Hours out of range 0-23: {sorted(bad)}")
    return out


def fetch(url: str, timeout: float, retries: int):
    """GET a jetta URL. Returns None on HTTP 404, raises RuntimeError on other failures."""
    req = urllib.request.Request(url, headers={"User-Agent": "tradedesk-jetta-backfill/1.0"})
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 404:
                    return None
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
            if e.code == 429:  # rate-limited: back off harder before retrying
                time.sleep(8.0)
                continue
        except Exception as e:  # URLError, socket timeout, JSON decode
            last = e
        if attempt < retries:
            time.sleep(1.0)
    raise RuntimeError(f"jetta fetch failed after {retries + 1} tries ({last})")


def pad(values, n: int) -> list[float]:
    arr = [float(x) for x in (values or [])]
    return (arr + [0.0] * n)[:n]


def encode_hour(doc: dict) -> bytes | None:
    """Encode one jetta hour document as LZMA bi5 bytes; None for an empty hour."""
    times = doc.get("times") or []
    asks = doc.get("asks") or []
    bids = doc.get("bids") or []
    if doc.get("ask") is None or doc.get("bid") is None or not times:
        return None
    n = len(times)
    if not (len(asks) == len(bids) == n):
        raise ValueError(f"ragged arrays: times={n} asks={len(asks)} bids={len(bids)}")

    mult = float(doc["multiplier"])
    if mult <= 0:
        raise ValueError(f"bad multiplier: {mult}")
    a0 = int(round(doc["ask"] / mult))
    b0 = int(round(doc["bid"] / mult))

    cum_t = list(itertools.accumulate(int(t) for t in times))
    if not (0 <= cum_t[-1] < 3_600_000):
        print(f"    warning: ticks span {cum_t[-1]} ms, outside one hour; check data", file=sys.stderr)

    vol_a = pad(doc.get("askVolumes"), n)
    vol_b = pad(doc.get("bidVolumes"), n)

    payload = bytearray()
    for ms, da, db, va, vb in zip(cum_t, itertools.accumulate(asks), itertools.accumulate(bids), vol_a, vol_b):
        payload += RECORD.pack(ms, a0 + int(da), b0 + int(db), va, vb)
    return lzma.compress(bytes(payload), format=lzma.FORMAT_ALONE)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Backfill tradedesk-dukascopy's .bi5 cache from jetta.dukascopy.com "
        "(fallback when datafeed.dukascopy.com is blocked)."
    )
    ap.add_argument("--symbol", required=True, help="e.g. NVDA.US/USD or EURUSD")
    ap.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD (UTC, inclusive)")
    ap.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD (UTC, inclusive)")
    ap.add_argument("--cache-dir", required=True, help="same --cache-dir the export uses")
    ap.add_argument("--hours", help="restrict to UTC hours, e.g. '13-21' or '14,15,16'")
    ap.add_argument("--timeout", type=float, default=15.0, help="per-request timeout seconds")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--force", action="store_true", help="re-fetch hours already in cache")
    args = ap.parse_args()

    try:
        hours_filter = parse_hours(args.hours)
        day = dt.date.fromisoformat(args.date_from)
        end = dt.date.fromisoformat(args.date_to)
    except ValueError as e:
        ap.error(str(e))
    if end < day:
        ap.error("--to is before --from")

    sym = symbol_norm(args.symbol)
    code = args.symbol.strip().replace("/", "-")  # NVDA.US/USD -> NVDA.US-USD
    if code == sym:
        print(f"note: symbol {args.symbol!r} has no .EXCH/CUR suffix; jetta code = {code}", file=sys.stderr)

    n_ok = n_empty = n_skip = n_fail = n_ticks = 0
    divisor_hint = None
    for cur in (day + dt.timedelta(days=i) for i in range((end - day).days + 1)):
        for hour in range(24):
            if hours_filter and hour not in hours_filter:
                continue
            cpath = (
                Path(args.cache_dir) / sym / f"{cur.year}" / f"{cur.month - 1:02d}"
                / f"{cur.day:02d}" / f"{hour:02d}h_ticks.bi5"
            )
            if cpath.exists() and not args.force:
                n_skip += 1
                continue
            if args.sleep > 0:
                time.sleep(args.sleep)
            url = JETTA_URL.format(code=code, y=cur.year, m=cur.month, d=cur.day, h=hour)
            try:
                doc = fetch(url, args.timeout, args.retries)
            except RuntimeError as e:
                print(f"  FAIL {cur} {hour:02d}h: {e}", file=sys.stderr)
                n_fail += 1
                continue
            cpath.parent.mkdir(parents=True, exist_ok=True)
            if doc is None:
                # jetta 404: unknown instrument or out-of-range date. Leave uncached so
                # the tool (which may still get it from the datafeed) can retry later.
                print(f"  404  {cur} {hour:02d}h: jetta has no such hour; left uncached", file=sys.stderr)
                n_fail += 1
                continue
            try:
                data = encode_hour(doc)
            except ValueError as e:
                print(f"  FAIL {cur} {hour:02d}h: {e}", file=sys.stderr)
                n_fail += 1
                continue
            if data is None:
                cpath.touch()  # closed hour: jetta answers 200 with empty arrays
                n_empty += 1
                continue
            tmp = cpath.with_suffix(cpath.suffix + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, cpath)
            n_ok += 1
            n_ticks += len(doc["times"])
            if divisor_hint is None:
                divisor_hint = round(1.0 / float(doc["multiplier"]))
            print(f"  ok   {cur} {hour:02d}h: {len(doc['times'])} ticks (multiplier {doc['multiplier']})")

    print(
        f"jetta backfill: {n_ok} hour(s) written ({n_ticks} ticks), "
        f"{n_empty} empty (cached as 0-byte), {n_skip} already cached, {n_fail} failed"
    )
    if n_fail:
        print("Failed hours were left uncached so a later run retries them.", file=sys.stderr)
        return 1
    hint = f' --price-divisor {divisor_hint}' if divisor_hint else ""
    print(
        f"Now re-run your usual tradedesk-dc-export command with --cache-dir {args.cache_dir}{hint} — "
        "it decodes these hours from cache with no datafeed access."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
(main())
