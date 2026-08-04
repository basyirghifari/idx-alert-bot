"""
Main entry point. Loops over your stock watchlist, fetches data via
yfinance, computes indicators, checks alert rules, and sends any
triggered alerts to Telegram. Designed to run on a schedule during
market hours (see .github/workflows/check.yml).
"""

from fetch_data import fetch_ohlcv
from indicators import add_indicators
from alert_rules import load_state, save_state, check_alerts
from telegram_bot import send_telegram_photo
from chart import generate_chart

# Edit this list to whatever IDX tickers you want to track.
# Yahoo Finance uses the ".JK" suffix for Indonesia Stock Exchange listings.
WATCHLIST = ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ASII.JK", "BMRI.JK"]

INTERVAL = "15m"   # candle timeframe
PERIOD = "5d"      # how far back to pull (must fit yfinance's interval limits,
                    # see comment at top of fetch_data.py)


def main():
    state = load_state()
    any_alerts = False

    for symbol in WATCHLIST:
        try:
            df = fetch_ohlcv(symbol, interval=INTERVAL, period=PERIOD)
            df = add_indicators(df)
            messages = check_alerts(symbol, df, state)

            if messages:
                any_alerts = True
                caption = "\n".join(messages)
                print(f"Sending alert for {symbol}:\n{caption}")
                chart_bytes = generate_chart(symbol, df)
                send_telegram_photo(chart_bytes, caption=caption)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    if not any_alerts:
        print("No alerts triggered this run.")

    save_state(state)


if __name__ == "__main__":
    main()
