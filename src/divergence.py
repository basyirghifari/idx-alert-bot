"""
Detects regular bullish divergence and hidden bullish divergence between
price and an indicator (RSI by default) — the same concept TradingView's
divergence indicators use.

Definitions:
- Regular bullish divergence: price makes a LOWER low, but the indicator
  makes a HIGHER low. Signals weakening downside momentum — often a
  reversal signal at the end of a downtrend.
- Hidden bullish divergence: price makes a HIGHER low, but the indicator
  makes a LOWER low. Signals the uptrend is likely to continue — a
  continuation signal during an uptrend pullback.

Both are detected by comparing the two most recent pivot lows in price
against the indicator's value at those same two points.
"""

import numpy as np
import pandas as pd


def find_pivot_lows(series: pd.Series, order: int = 3) -> list:
    """
    Returns the positional indices where `series` has a local minimum —
    i.e. lower than every value within `order` bars on both sides.
    """
    values = series.values
    n = len(values)
    pivots = []
    for i in range(order, n - order):
        window = values[i - order: i + order + 1]
        if values[i] == window.min() and (window == values[i]).sum() == 1:
            pivots.append(i)
    return pivots


def detect_bullish_divergence(df: pd.DataFrame, indicator_col: str = "rsi",
                               price_col: str = "low", order: int = 3,
                               lookback: int = 60, freshness: int = None) -> dict | None:
    """
    Looks at the last `lookback` candles, finds the two most recent pivot
    lows in `price_col`, and compares them against `indicator_col` to spot
    a divergence. Only returns a result if the most recent pivot is fresh
    (within `freshness` bars of the end of the window) — otherwise this
    would keep re-detecting the same old divergence every run.

    Returns None if no divergence is found, otherwise a dict:
    {
        "type": "regular_bullish" | "hidden_bullish",
        "pivot1_idx": int, "pivot2_idx": int,   # positions within the last `lookback` candles
        "price1": float, "price2": float,
        "ind1": float, "ind2": float,
    }
    """
    if freshness is None:
        freshness = order + 3

    recent = df.tail(lookback).reset_index(drop=True)
    pivots = find_pivot_lows(recent[price_col], order=order)
    if len(pivots) < 2:
        return None

    i1, i2 = pivots[-2], pivots[-1]

    # Only alert on a freshly-confirmed pivot, not one from many candles ago
    if i2 < len(recent) - freshness:
        return None

    price1, price2 = recent[price_col].iloc[i1], recent[price_col].iloc[i2]
    ind1, ind2 = recent[indicator_col].iloc[i1], recent[indicator_col].iloc[i2]

    if pd.isna(ind1) or pd.isna(ind2):
        return None

    if price2 < price1 and ind2 > ind1:
        div_type = "regular_bullish"
    elif price2 > price1 and ind2 < ind1:
        div_type = "hidden_bullish"
    else:
        return None

    return {
        "type": div_type,
        "pivot1_idx": i1, "pivot2_idx": i2,
        "price1": float(price1), "price2": float(price2),
        "ind1": float(ind1), "ind2": float(ind2),
    }
