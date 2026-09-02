"""Demand / Supply zone viewer for XAUUSD + BTCUSD (Kingade scalper).

Usage:
  python zone_detector.py [--symbol XAUUSD,BTCUSD] [--tf M1|M5] [--bars N]
"""
import argparse
import sys
import MetaTrader5 as mt5

sys.path.insert(0, ".")
import mt5_connector as mt5c
from zones import build_zones

TF_MAP = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSD,BTCUSD")
    ap.add_argument("--tf", default="M5")
    ap.add_argument("--bars", type=int, default=1500)
    ap.add_argument("--clusters", type=int, default=8)
    args = ap.parse_args()
    tf = TF_MAP.get(args.tf.upper(), mt5.TIMEFRAME_M5)

    mt5.initialize()
    for sym in args.symbol.split(","):
        df = mt5c.get_ohlc(sym, tf, args.bars)
        if df is None or len(df) < 200:
            print(f"{sym}: insufficient data")
            continue
        zones, avg_atr = build_zones(df, symbol=sym, min_touches=2)
        close = float(df["close"].iloc[-1])
        for z in zones:
            z["dist"] = z["mid"] - close
        zones.sort(key=lambda z: abs(z["dist"]))
        print("=" * 70)
        print(f"{sym}  {args.tf.upper()}  last {len(df)} bars  |  "
              f"current close = {close:.2f}  (ATR ~{avg_atr:.3f})")
        print("=" * 70)
        print(f"{'KIND':<8}{'range':>22}{'tch':>5}{'age':>6}{'str':>6}{'dist':>10}  note")
        for z in zones[:args.clusters]:
            below = z["mid"] < close
            if z["kind"] == "demand":
                note = "support BELOW price" if below else "demand above price"
            else:
                note = "resistance ABOVE price" if not below else "supply below price"
            print(f"{z['kind']:8}"
                  f"{z['bottom']:13.2f}-{z['top']:.2f}"
                  f"{z['touches']:>5}{z['age_bars']:>6}{z['strength']:>6.2f}"
                  f"{z['dist']:>10.2f}  {note}")
    mt5.shutdown()


if __name__ == "__main__":
    main()
