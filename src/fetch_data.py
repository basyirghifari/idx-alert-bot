"""
Fetches recent OHLCV candle data for an Indonesia Stock Exchange (IDX)
ticker using yfinance. No API key required.

IDX tickers on Yahoo Finance use a ".JK" suffix, e.g. "BBCA.JK" for
Bank Central Asia, "TLKM.JK" for Telkom Indonesia.

Note on yfinance interval/period limits (Yahoo Finance restrictions,
not something we control):
  - "1m"  data: only available for the last 7 days
  - "5m","15m","30m" data: only available for the last 60 days
  - "1h"  data: only available for the last 730 days
  - "1d" and above: full history available
So the `period` passed to fetch_ohlcv must fit within those windows.
"""

import pandas as pd
import yfinance as yf


def fetch_ohlcv(symbol: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
    """
    Fetch candle data for a given ticker.

    symbol: e.g. "BBCA.JK", "TLKM.JK", "ASII.JK" (IDX tickers need the ".JK" suffix)
    interval: "1m", "5m", "15m", "30m", "1h", "1d", etc.
    period: how far back to fetch, e.g. "5d", "1mo", "1y"
            (must respect yfinance's interval limits above)
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for {symbol} (interval={interval}, period={period})")

    df = df.reset_index()
    time_col = "Datetime" if "Datetime" in df.columns else "Date"

    df = df.rename(columns={
        time_col: "open_time",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    return df[["open_time", "open", "high", "low", "close", "volume"]]


if __name__ == "__main__":
    data = fetch_ohlcv("BBCA.JK", interval="15m", period="5d")
    print(data.tail())
