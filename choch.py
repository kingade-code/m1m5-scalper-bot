# CHoCH (Change of Character) detector
# Identifies trend reversals by detecting break of structure
import logging

logger = logging.getLogger(__name__)


def detect_choch(df, direction, lookback=20):
    """Detect Change of Character (CHoCH) on a dataframe.
    
    Bullish CHoCH: Price was making lower lows, then breaks above the most recent swing high.
    Bearish CHoCH: Price was making higher highs, then breaks below the most recent swing low.
    
    Args:
        df: DataFrame with OHLC columns
        direction: "bullish" or "bearish" - the direction we want to trade
        lookback: Number of bars to look back for structure
    
    Returns:
        True if CHoCH confirms the direction, False otherwise
    """
    if len(df) < lookback + 5:
        return False
    
    recent = df.iloc[-lookback:]
    
    # Find swing highs and lows
    swing_highs = []
    swing_lows = []
    
    for i in range(2, len(recent) - 2):
        bar = recent.iloc[i]
        prev1 = recent.iloc[i-1]
        prev2 = recent.iloc[i-2]
        next1 = recent.iloc[i+1]
        next2 = recent.iloc[i+2]
        
        # Swing high: higher than 2 bars before and after
        if bar['high'] > prev1['high'] and bar['high'] > prev2['high'] and \
           bar['high'] > next1['high'] and bar['high'] > next2['high']:
            swing_highs.append((i, bar['high']))
        
        # Swing low: lower than 2 bars before and after
        if bar['low'] < prev1['low'] and bar['low'] < prev2['low'] and \
           bar['low'] < next1['low'] and bar['low'] < next2['low']:
            swing_lows.append((i, bar['low']))
    
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return False
    
    current_price = df.iloc[-1]['close']
    
    if direction == "bullish":
        # Bullish CHoCH: recent swing lows were descending (lower lows),
        # then price breaks above the most recent swing high
        last_two_lows = swing_lows[-2:]
        if last_two_lows[1][1] < last_two_lows[0][1]:  # Lower low formed
            # Check if price broke above last swing high
            last_high = swing_highs[-1][1]
            if current_price > last_high:
                logger.debug(f"CHoCH bullish: broke above {last_high:.5f}")
                return True
    
    elif direction == "bearish":
        # Bearish CHoCH: recent swing highs were ascending (higher highs),
        # then price breaks below the most recent swing low
        last_two_highs = swing_highs[-2:]
        if last_two_highs[1][1] > last_two_highs[0][1]:  # Higher high formed
            # Check if price broke below last swing low
            last_low = swing_lows[-1][1]
            if current_price < last_low:
                logger.debug(f"CHoCH bearish: broke below {last_low:.5f}")
                return True
    
    return False


def detect_bos(df, direction, lookback=20):
    """Detect Break of Structure (BOS) - simpler version of CHoCH.
    
    BOS: Price breaks the most recent swing high (bullish) or swing low (bearish)
    without requiring the structure to be reversing.
    
    Args:
        df: DataFrame with OHLC columns
        direction: "bullish" or "bearish"
        lookback: Number of bars to look back
    
    Returns:
        True if BOS confirms the direction, False otherwise
    """
    if len(df) < lookback + 5:
        return False
    
    recent = df.iloc[-lookback:]
    
    swing_highs = []
    swing_lows = []
    
    for i in range(2, len(recent) - 2):
        bar = recent.iloc[i]
        prev1 = recent.iloc[i-1]
        prev2 = recent.iloc[i-2]
        next1 = recent.iloc[i+1]
        next2 = recent.iloc[i+2]
        
        if bar['high'] > prev1['high'] and bar['high'] > prev2['high'] and \
           bar['high'] > next1['high'] and bar['high'] > next2['high']:
            swing_highs.append((i, bar['high']))
        
        if bar['low'] < prev1['low'] and bar['low'] < prev2['low'] and \
           bar['low'] < next1['low'] and bar['low'] < next2['low']:
            swing_lows.append((i, bar['low']))
    
    if not swing_highs or not swing_lows:
        return False
    
    current_price = df.iloc[-1]['close']
    
    if direction == "bullish" and swing_highs:
        last_high = swing_highs[-1][1]
        if current_price > last_high:
            return True
    
    if direction == "bearish" and swing_lows:
        last_low = swing_lows[-1][1]
        if current_price < last_low:
            return True
    
    return False
