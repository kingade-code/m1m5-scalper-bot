# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Trailing-stop sweep for the current Kingade pattern strategy. Holds the
whole engine fixed (trend filter, wick SL, 1:4 RR, max-bars, cooldown, risk,
0.30 spread + 0.10 stop-slippage) and only varies TRAIL_START_ATR /
TRAIL_STEP_ATR plus a no-trailing baseline. Each config runs in an isolated
subprocess; results are check-pointed to trail_comparison.json.
"""
import json
import subprocess
import sys
import os

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
OUT = os.path.join(BASE, "trail_comparison.json")

STARTS = [0.0, 0.2, 0.3, 0.5, 0.8, 1.2, 2.0] + [0.0, 0.3, 0.8]
STEPS = [0.1, 0.2, 0.3, 0.5] + [0.7, 1.0, 1.5]
LEGS = [  # (tf, months, mode, label)
    ("TIMEFRAME_M5", 16, "own", "M5"),
    ("TIMEFRAME_M1", 50, "m1", "M1"),
]


def configs():
    yield ("-", "-", "no_trail")
    for s in STARTS:
        for st in STEPS:
            yield (f"{s:g}", f"{st:g}", f"{s:g}/{st:g}")


def _load():
    if os.path.exists(OUT):
        with open(OUT, "r") as f:
            return json.load(f)
    return {}


def _merge(data, label, key):
    f = os.path.join(BASE, f"_res_trail_{label}_{key.replace('/', '_')}.json")
    if not os.path.exists(f):
        print(f"[no-result] {label}/{key}")
        return
    with open(f, "r") as fh:
        j = json.load(fh)
    data[label][key] = j
    print(f"[ok] {label}/{key}: {j['net_pct']}%  WR {j['win_rate']}%  "
          f"PF {j['pf']}  avgRR {j['avg_rr']}  ({j['trades']} T)")
    os.remove(f)


def main():
    data = _load()
    for tf, months, mode, label in LEGS:
        data.setdefault(label, {})
        for s, st, key in configs():
            if key in data[label]:
                print(f"[skip] {label}/{key} already done")
                continue
            cmd = [sys.executable, "trail_sweep_worker.py",
                   tf, str(months), mode, label, s, st]
            try:
                rc = subprocess.call(cmd, cwd=BASE, timeout=2700)
            except subprocess.TimeoutExpired:
                print(f"[timeout] {label}/{key}")
                continue
            if rc != 0:
                print(f"[failed] {label}/{key}: rc={rc}")
                continue
            _merge(data, label, key)
            with open(OUT, "w") as f:
                json.dump(data, f, indent=2)
    print("done")


if __name__ == "__main__":
    main()