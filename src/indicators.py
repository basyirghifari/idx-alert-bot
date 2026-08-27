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

    df["rsi"] = ta.rsi(df["close"], length=14)

    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    # macd columns will be named: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

    df["ema_20"] = ta.ema(df["close"], length=20)
    df["ema_50"] = ta.ema(df["close"], length=50)

    df["volume_avg_20"] = df["volume"].rolling(window=20).mean()

    # ATR (Average True Range) — used by ai_analysis.py as a volatility
    # baseline for entry/TP/SL suggestions, and as the fallback calculation
    # if the AI call fails or isn't configured.
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    return df
