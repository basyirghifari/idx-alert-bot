"""
Main entry point. Loops over your stock watchlist, fetches data via
yfinance, computes indicators, checks alert rules, and sends any
triggered alerts to Telegram. Designed to run on a schedule during
market hours (see .github/workflows/check.yml).
"""

from fetch_data import fetch_ohlcv
from indicators import add_indicators
from alert_rules import load_state, save_state, check_alerts
from telegram_bot import send_telegram_message

# Edit this list to whatever IDX tickers you want to track.
# Yahoo Finance uses the ".JK" suffix for Indonesia Stock Exchange listings.
WATCHLIST = ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ASII.JK", "BMRI.JK"]

INTERVAL = "15m"   # candle timeframe
PERIOD = "5d"      # how far back to pull (must fit yfinance's interval limits,
                    # see comment at top of fetch_data.py)


def main():
    state = load_state()
    all_messages = []

    for symbol in WATCHLIST:
        try:
            df = fetch_ohlcv(symbol, interval=INTERVAL, period=PERIOD)
            df = add_indicators(df)
            messages = check_alerts(symbol, df, state)
            all_messages.extend(messages)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    if all_messages:
        full_text = "\n".join(all_messages)
        print("Sending alert:\n", full_text)
        send_telegram_message(full_text)
    else:
        print("No alerts triggered this run.")

    save_state(state)


if __name__ == "__main__":
    main()
