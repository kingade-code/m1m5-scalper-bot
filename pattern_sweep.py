# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Orchestrates the all-pattern sweep. Each (leg, pattern) run is a fresh
subprocess so a single hang/crash can't kill the sweep; JSON is check-pointed
after every pattern. The worker imports cached_get_ohlc from here.
"""
import json
import subprocess
import sys
import os
import backtest_m1_trend as bt

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
OUT = os.path.join(BASE, "pattern_comparison.json")
SPREAD, SLIP = 0.30, 0.10
_REAL_GET = bt.get_ohlc  # captured before any worker-side patching
PATTERN_ORDER = [
    "current", "hammer", "shooting_star", "engulfing", "doji",
    "dragonfly_doji", "gravestone_doji", "marubozu", "harami",
    "inside_bar", "tweezer", "morning_star", "evening_star",
    "three_white_soldiers", "three_black_crows",
]
LEGS = [  # (tf, months, mode, label)
    ("TIMEFRAME_M5", 16, "own", "M5"),
    ("TIMEFRAME_M1", 50, "m1", "M1"),
]

_cache = {}


def cached_get_ohlc(symbol, tf, count):
    key = (symbol, int(tf), count)
    if key not in _cache:
        _cache[key] = _REAL_GET(symbol, tf, count)
    return _cache[key]


def _load():
    if os.path.exists(OUT):
        with open(OUT, "r") as f:
            return json.load(f)
    return {}


def _merge_result(data, label, pattern):
    f = os.path.join(BASE, f"_res_{label}_{pattern}.json")
    if not os.path.exists(f):
        print(f"[no-result] {label}/{pattern}")
        return
    with open(f, "r") as fh:
        j = json.load(fh)
    data[label][pattern] = j
    print(f"[ok]   {label}/{pattern}: {j['net_pct']}%  "
          f"WR {j['win_rate']}%  PF {j['pf']}  ({j['trades']} T)")
    os.remove(f)


def main():
    data = _load()
    for tf, months, mode, label in LEGS:
        data.setdefault(label, {})
        for p in PATTERN_ORDER:
            if p in data[label]:
                print(f"[skip] {label}/{p} already done")
                continue
            cmd = [sys.executable, "pattern_sweep_worker.py",
                   tf, str(months), mode, label, p]
            try:
                rc = subprocess.call(cmd, cwd=BASE, timeout=2700)
            except subprocess.TimeoutExpired:
                print(f"[timeout] {label}/{p}")
                continue
            if rc != 0:
                print(f"[failed] {label}/{p}: rc={rc}")
                continue
            _merge_result(data, label, p)
            with open(OUT, "w") as f:
                json.dump(data, f, indent=2)
    print("done")


if __name__ == "__main__":
    main()