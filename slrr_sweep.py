# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""SL-buffer x R:R sweep, trailing ON at live 0.3/0.1. Aim: find whether a
tighter stop combined with a larger target ratio improves the strategy.
PIP_BUFFER (price above/below the signal wick) shrinks the SL; RR_RATIO
scales the take-profit. Everything else fixed (current pattern strategy,
cooldown, max-bars, reverse-close, risk, 0.30 spread + 0.10 slip).
Check-pointed to slrr_comparison.json.
"""
import json
import subprocess
import sys
import os

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
OUT = os.path.join(BASE, "slrr_comparison.json")

BUFFERS = [0.1, 0.2, 0.3, 0.5]   # 0.5 = live (5 pips)
RRS = [2, 3, 4, 6, 8, 10]
LEGS = [  # (tf, months, mode, label)
    ("TIMEFRAME_M5", 16, "own", "M5"),
    ("TIMEFRAME_M1", 50, "m1", "M1"),
]


def _load():
    if os.path.exists(OUT):
        with open(OUT, "r") as f:
            return json.load(f)
    return {}


def _merge(data, label, buf, rr):
    f = os.path.join(BASE, f"_res_slrr_{label}_{str(buf).replace('.', 'p')}_{rr}.json")
    if not os.path.exists(f):
        print(f"[no-result] {label}/b{buf}/1:{rr}")
        return
    with open(f, "r") as fh:
        j = json.load(fh)
    data[label][f"b{str(buf).replace('.', 'p')}/1:{rr}"] = j
    print(f"[ok] {label}/b{buf}/1:{rr}: {j['net_pct']}%  WR {j['win_rate']}%  "
          f"PF {j['pf']}  avgRR {j['avg_rr']}  ({j['trades']} T)")
    os.remove(f)


def main():
    data = _load()
    for tf, months, mode, label in LEGS:
        data.setdefault(label, {})
        for buf in BUFFERS:
            for rr in RRS:
                key = f"b{str(buf).replace('.', 'p')}/1:{rr}"
                if key in data[label]:
                    print(f"[skip] {label}/{key} already done")
                    continue
                cmd = [sys.executable, "slrr_sweep_worker.py",
                       tf, str(months), mode, label, str(buf), str(rr)]
                try:
                    rc = subprocess.call(cmd, cwd=BASE, timeout=2700)
                except subprocess.TimeoutExpired:
                    print(f"[timeout] {label}/{key}")
                    continue
                if rc != 0:
                    print(f"[failed] {label}/{key}: rc={rc}")
                    continue
                _merge(data, label, buf, rr)
                with open(OUT, "w") as f:
                    json.dump(data, f, indent=2)
    print("done")


if __name__ == "__main__":
    main()