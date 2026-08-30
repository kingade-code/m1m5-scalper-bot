# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Reward-multiple sweep with the trailing stop DISABLED: every trade is a
pure TP-or-SL decision at a fixed R:R from 1:1 to 1:15. Engine otherwise
identical (hammer/shooting-star/engulfing, wick SL, cooldown, max-bars,
reverse-close, risk, 0.30 spread + 0.10 stop-slippage). Isolated subprocesses
per config, check-pointed to rr_comparison.json.
"""
import json
import subprocess
import sys
import os

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
OUT = os.path.join(BASE, "rr_comparison.json")

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
    f = os.path.join(BASE, f"_res_rr_{label}_{ratio}.json")
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
            cmd = [sys.executable, "rr_sweep_worker.py",
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