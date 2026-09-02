"""Demand / Supply zone detection reused by the live bot.

Bottom-up: cluster swing pivots into zones, mark supply (from swing highs)
and demand (from swing lows). Zones are ATR-scaled so the same thresholds
work for gold and BTC. Provides a greedy nearest-zone lookup used by the
bot's optional zone-based entry filter.
"""
import numpy as np
import pandas as pd
import config
import swing_detector as sw


def build_zones(df, symbol=None,
                swing_strength=None,
                min_touches=2,
                cluster_atr=0.5,
                max_span_atr=3.0,
                min_span_atr=0.15,
                atr_period=None,
                max_zones=20):
    """Detect demand/supply zones from OHLC bars.

    Zones are clustered from swing pivots. A zone is only kept if it has at
    least `min_touches` pivot members and its span (top-bottom) is within
    [min_span_atr, max_span_atr] * ATR -- this rejects both tiny noise and
    over-merged mega-zones.

    Returns (zones, avg_atr) where each zone is:
      {"kind": "demand"|"supply", "top", "bottom", "mid", "touches",
       "age_bars", "span_atr", "strength"}
    """
    if atr_period is None:
        atr_period = int(config.get_symbol_param(symbol, "ATR_PERIOD", config.ATR_PERIOD))
    if swing_strength is None:
        swing_strength = int(config.get_symbol_param(symbol, "SWING_STRENGTH", config.SWING_STRENGTH))

    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    n = len(df)

    # ATR series (used purely as the clustering scale)
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1])))
    atr_series = pd.Series(tr).rolling(atr_period, min_periods=1).mean().to_numpy()

    sh = sw.find_swing_highs(pd.Series(high), strength=swing_strength)
    sl = sw.find_swing_lows(pd.Series(low), strength=swing_strength)
    sh_idx = [i for i, _ in sh]
    sl_idx = [i for i, _ in sl]

    avg_atr = float(np.nanmean(atr_series[-300:])) if len(atr_series) else 0
    if avg_atr <= 0:
        avg_atr = float(np.nanmean(high - low)) if n else 1.0
    if avg_atr <= 0:
        avg_atr = 1.0
    cluster = cluster_atr * avg_atr
    min_span = min_span_atr * avg_atr
    max_span = max_span_atr * avg_atr

    demand = _cluster(sl_idx, low, cluster, min_span, max_span)
    supply = _cluster(sh_idx, high, cluster, min_span, max_span)
    for dz in demand:
        dz["kind"] = "demand"
    for sz in supply:
        sz["kind"] = "supply"

    zones = demand + supply
    zones = [z for z in zones if z["touches"] >= min_touches]
    zones.sort(key=lambda z: z["mid"])
    return zones[:max_zones], avg_atr


def _cluster(pivot_idxs, price, cluster, min_span, max_span):
    """Group swing pivots within `cluster` price units into zones,
    keeping only those whose span is within [min_span, max_span]."""
    ids = sorted(pivot_idxs)
    groups = []
    for i in ids:
        placed = False
        for g in groups:
            if abs(price[i] - price[g["anchor"]]) <= cluster:
                g["members"].append(i)
                g["anchor"] = i  # newest pivot is the anchor
                placed = True
                break
        if not placed:
            groups.append({"members": [i], "anchor": i})

    zones = []
    for g in groups:
        tops = [price[m] for m in g["members"]]
        top, bottom = max(tops), min(tops)
        span = top - bottom
        if span < min_span or span > max_span:
            continue
        idxs = g["members"]
        zones.append({
            "members": idxs,
            "top": top,
            "bottom": bottom,
            "mid": (top + bottom) / 2,
            "touches": len(idxs),
            "age_bars": (len(price) - 1) - max(idxs),
            "span_atr": span / (max_span / 3.0 if max_span else 1.0),
            "strength": min(1.0, len(idxs) / 5.0) *
                        min(1.0, 1.5 / max(span / (max_span if max_span else 1), 0.5)),
        })
    return zones


def _nearest_zone(zones, price, kind):
    """Greedy nearest zone of a given kind to `price` (within tolerance)."""
    best = None
    best_dist = float("inf")
    for z in zones:
        if z["kind"] != kind:
            continue
        # distance from price to the zone band (0 if inside)
        if z["bottom"] <= price <= z["top"]:
            d = 0.0
        else:
            d = min(abs(price - z["bottom"]), abs(price - z["top"]))
        if d < best_dist:
            best_dist = d
            best = z
    return best, best_dist


def get_zone_context(symbol, df, direction, current_price):
    """Return the demand/supply zone most relevant to a signal direction.

    direction: 'bullish' -> want a nearby demand (support) zone to bounce off
               'bearish' -> want a nearby supply (resistance) zone to reject
    Returns (zone, dist) or (None, inf).
    """
    zones, avg_atr = build_zones(df, symbol=symbol)
    if direction == "bullish":
        zone, dist = _nearest_zone(zones, current_price, "demand")
    else:
        zone, dist = _nearest_zone(zones, current_price, "supply")
    return zone, dist, avg_atr


def check_zone_filter(symbol, df, direction, current_price):
    """Optional zone filter: only allow a signal if price is close to a
    supportive demand zone (bullish) or resistive supply zone (bearish).

    proximity is measured in ATR units via ZONE_MAX_DIST_ATR (0 disables).
    Returns True if the signal is allowed.
    """
    max_dist = float(config.get_symbol_param(symbol, "ZONE_MAX_DIST_ATR", 0))
    if max_dist <= 0:
        return True
    zone, dist, avg_atr = get_zone_context(symbol, df, direction, current_price)
    if zone is None:
        return False
    return dist <= max_dist * avg_atr
