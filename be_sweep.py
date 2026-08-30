# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Breakeven+2pip-at-2R sweep. Trailing stop is OFF; instead, the instant a
trade reaches 2R of profit the stop jumps to entry +/- 2 pips (guaranteed
small win) and the rest runs toward the tested R:R target. Same cost model
and engine. Isolated subprocesses, check-pointed to be_comparison.json.
"""
import json
import subprocess
import sys
import os

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
OUT = os.path.join(BASE, "be_comparison.json")

RRS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15]
LEGS = [  # (tf, months, mode, label)
    ("TIMEFRAME_M5", 16, "own", "M5"),
    ("TIMEFRAME_M1", 50, "m1", "M1"),
]


def _load():
    if os.path.exists(OUT):
        with open(OUT, "r") as f:
            return json.load(f)
    return {}


def _merge(data, label, ratio):
    f = os.path.join(BASE, f"_res_be_{label}_{ratio}.json")
    if not os.path.exists(f):
        print(f"[no-result] {label}/1:{ratio}")
        return
    with open(f, "r") as fh:
        j = json.load(fh)
    data[label][str(ratio)] = j
    print(f"[ok] {label}/1:{ratio}: {j['net_pct']}%  WR {j['win_rate']}%  "
          f"PF {j['pf']}  avgRR {j['avg_rr']}  ({j['trades']} T)")
    os.remove(f)


def main():
    data = _load()
    for tf, months, mode, label in LEGS:
        data.setdefault(label, {})
        for ratio in RRS:
            key = str(ratio)
            if key in data[label]:
                print(f"[skip] {label}/1:{ratio} already done")
                continue
            cmd = [sys.executable, "be_sweep_worker.py",
                   tf, str(months), mode, label, str(ratio)]
            try:
                rc = subprocess.call(cmd, cwd=BASE, timeout=2700)
            except subprocess.TimeoutExpired:
                print(f"[timeout] {label}/1:{ratio}")
                continue
            if rc != 0:
                print(f"[failed] {label}/1:{ratio}: rc={rc}")
                continue
            _merge(data, label, ratio)
            with open(OUT, "w") as f:
                json.dump(data, f, indent=2)
    print("done")


if __name__ == "__main__":
    main()