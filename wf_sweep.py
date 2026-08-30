# Copyright (c) 2026 Kingade Forex. All rights reserved.
"""Walk-forward split of the current strategy over the downloaded CSV.

Phase 1 (TRAIN, fits parameters): trailing-stop grid on 2023-01-02 ->
2025-06-30, M5 leg only. That window contains ~2.5 years the parameter
sweeps NEVER saw (they were tuned on the recent 6 months).
Phase 2 (TEST, blind): the current live config + the top train configs +
the recent-window favourite 0.0/0.1 are frozen as-is and run on
2025-07-01 -> 2026-08-26, both legs. No parameter is tuned on the test set.
Checkpointed to wf_train_comparison.json / wf_test_comparison.json.
"""
import json
import os
import subprocess
import sys

BASE = r"C:\Users\kinga\Documents\My Site\M1-M5 scalping"
TRAIN_OUT = os.path.join(BASE, "wf_train_comparison.json")
TEST_OUT = os.path.join(BASE, "wf_test_comparison.json")

TRAIN = ("2023-01-02", "2025-06-30")
TEST = ("2025-07-01", "2026-08-26")

STARTS = [0.0, 0.2, 0.3, 0.5, 0.8, 1.2, 2.0]
STEPS = [0.1, 0.2, 0.3, 0.5]
N_TRAIN_PICKS = 3


def _load(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _run(desc, start, end, leg, trail, rr, outfile, data, key):
    """Run one config; store into data[key]."""
    if key in data:
        print(f"[skip] {key}")
        return
    cmd = [sys.executable, "wf_sweep_worker.py", start, end, leg,
           trail, str(rr), outfile]
    try:
        rc = subprocess.call(cmd, cwd=BASE, timeout=2700)
    except subprocess.TimeoutExpired:
        print(f"[timeout] {key}")
        return
    if rc != 0:
        print(f"[failed] {key}: rc={rc}")
        return
    f = os.path.join(BASE, outfile)
    if not os.path.exists(f):
        print(f"[no-result] {key}")
        return
    with open(f, "r") as fh:
        data[key] = json.load(fh)
    print(f"[ok] {key}: {data[key]['net_pct']}%  WR {data[key]['win_rate']}%  "
          f"PF {data[key]['pf']}  ({data[key]['trades']} T)")
    os.remove(f)


def phase1_train():
    data = _load(TRAIN_OUT)
    for s in STARTS:
        for step in STEPS:
            key = f"{s}/{step}"
            _run("train", *TRAIN, "M5", f"{s}/{step}", 4.0,
                 f"_res_wf_{key.replace('/', 'p')}_train.json", data, key)
    key = "no_trail"
    _run("train", *TRAIN, "M5", "None", 4.0,
         "_res_wf_notrail_train.json", data, key)
    _save(TRAIN_OUT, data)
    top = sorted(data.items(), key=lambda kv: kv[1]["net_pct"], reverse=True)
    picks = [k for k, _ in top[:N_TRAIN_PICKS]]
    print("TRAIN best:", [(k, round(data[k]['net_pct'], 1)) for k in picks])
    return picks


def phase2_test(picks):
    data = _load(TEST_OUT)
    wait = set(picks) | {"0.3/0.1", "0.0/0.1"}
    for key in sorted(wait):
        for leg in ("M5", "M1"):
            dk = f"{leg}:{key}"
            _run("test", *TEST, leg, key, 4.0,
                 f"_res_wf_{leg}_{key.replace('/', 'p')}_test.json", data, dk)
    _save(TEST_OUT, data)
    print("TEST (blind):")
    for dk in data:
        m = data[dk]
        print(f"  {dk}: {m['net_pct']}%  WR {m['win_rate']}%  "
              f"PF {m['pf']}  ({m['trades']} T)")


def main():
    picks = phase1_train()
    phase2_test(picks)
    print("done")


if __name__ == "__main__":
    main()