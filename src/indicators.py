"""
Computes technical indicators on OHLCV data using pandas-ta.
"""

import pandas as pd
import pandas_ta as ta


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds RSI, MACD, and EMA columns to the dataframe.
    Expects columns: open, high, low, close, volume
    """
    df = df.copy()

    # RSI (14-period default)
    df["rsi"] = ta.rsi(df["close"], length=14)

    # MACD (12, 26, 9 default)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    # macd columns will be named: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

    # EMAs for trend context
    df["ema_20"] = ta.ema(df["close"], length=20)
    df["ema_50"] = ta.ema(df["close"], length=50)

    # Volume average for spike detection
    df["volume_avg_20"] = df["volume"].rolling(window=20).mean()

    return df
