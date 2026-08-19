import logging
import config

logger = logging.getLogger(__name__)


def calculate_retracement_levels(swing_high_price, swing_low_price, direction):
    """Calculate Fibonacci retracement levels based on swing points.

    For bullish (buying the dip):
        Price moved UP from swing_low to swing_high, now retracing DOWN.
        Retracement levels go downward from swing_high.
        Extensions go ABOVE swing_high (continuation targets).

    For bearish (selling the rally):
        Price moved DOWN from swing_high to swing_low, now retracing UP.
        Retracement levels go upward from swing_low.
        Extensions go BELOW swing_low (continuation targets).

    Returns dict of level_name -> price.
    """
    price_range = swing_high_price - swing_low_price
    if price_range <= 0:
        return None

    levels = {}

    if direction == "bullish":
        # Retracement levels (measured from swing_high downward)
        levels["0.0"] = swing_high_price
        levels["0.382"] = swing_high_price - price_range * 0.382
        levels["0.5"] = swing_high_price - price_range * 0.5
        levels["0.618"] = swing_high_price - price_range * 0.618
        levels["0.786"] = swing_high_price - price_range * 0.786
        levels["1.0"] = swing_low_price
        # Extension levels ABOVE swing_high (continuation targets for buy)
        levels["1.272"] = swing_high_price + price_range * 0.272
        levels["1.618"] = swing_high_price + price_range * 0.618

    elif direction == "bearish":
        # Retracement levels (measured from swing_low upward)
        levels["0.0"] = swing_low_price
        levels["0.382"] = swing_low_price + price_range * 0.382
        levels["0.5"] = swing_low_price + price_range * 0.5
        levels["0.618"] = swing_low_price + price_range * 0.618
        levels["0.786"] = swing_low_price + price_range * 0.786
        levels["1.0"] = swing_high_price
        # Extension levels BELOW swing_low (continuation targets for sell)
        levels["1.272"] = swing_low_price - price_range * 0.272
        levels["1.618"] = swing_low_price - price_range * 0.618

    return levels


def get_entry_zone(levels, direction):
    """Get the entry zone (0.5 to 0.786) and determine entry/SL/TP prices.

    Returns dict:
        entry_zone_high, entry_zone_low: the entry zone boundaries
        entry_price: ideal entry (midpoint of zone)
        sl: stop-loss beyond the invalidation point
        tp1: first take-profit at 1.272 extension
        tp2: second take-profit at 1.618 extension
        direction: 'buy' or 'sell'
    """
    if levels is None:
        return None

    zone_high = levels["0.786"]
    zone_low = levels["0.5"]
    entry_mid = (zone_high + zone_low) / 2.0

    # Enforce minimum zone width (0.1% of mid price)
    min_zone = entry_mid * 0.001
    if abs(zone_high - zone_low) < min_zone:
        zone_high = entry_mid + min_zone / 2
        zone_low = entry_mid - min_zone / 2

    result = {
        "entry_zone_high": zone_high,
        "entry_zone_low": zone_low,
        "entry_price": entry_mid,
        "all_levels": levels,
    }

    if direction == "bullish":
        result["direction"] = "buy"
        # SL at swing_low (1.0 level) - below the entry zone
        result["sl"] = levels["1.0"]
        # TP at extensions above swing_high
        result["tp1"] = levels["1.272"]
        result["tp2"] = levels["1.618"]
    else:
        result["direction"] = "sell"
        # SL at swing_high (1.0 level) - above the entry zone
        result["sl"] = levels["1.0"]
        # TP at extensions below swing_low
        result["tp1"] = levels["1.272"]
        result["tp2"] = levels["1.618"]

    return result


def is_price_in_entry_zone(current_price, entry_zone):
    """Check if current price is within the 0.618-0.786 entry zone."""
    if entry_zone is None:
        return False
    zone_high = entry_zone["entry_zone_high"]
    zone_low = entry_zone["entry_zone_low"]
    return zone_low <= current_price <= zone_high


def calculate_sl_distance(entry_price, sl_price):
    """Calculate the absolute SL distance in price."""
    return abs(entry_price - sl_price)
