"""
Checks every OPEN position logged in Google Sheets against the latest
price and marks it TP_HIT (win) or SL_HIT (loss) if the price has reached
either level. Runs once per workflow execution, before evaluating new
alerts, so a position that resolves gets closed out and reported.

This only looks at whichever level (TP or SL) the current price has
reached — it doesn't reconstruct which one was hit first intra-candle if
both were crossed within the same 15-minute check window. For a free,
15-minute-cadence bot this is an acceptable approximation.
"""

from google_sheets import get_open_positions, update_position
from fetch_data import fetch_ohlcv


def check_open_positions(send_notification=None):
    """
    send_notification: optional callable(text: str) -> None, e.g.
    telegram_bot.send_telegram_message, called once per resolved position.
    """
    try:
        positions = get_open_positions()
    except Exception as e:
        print(f"Could not read open positions from Google Sheets: {e}")
        return

    if not positions:
        print("No open positions to check.")
        return

    symbols = {p["symbol"] for p in positions}
    latest_prices = {}
    for symbol in symbols:
        try:
            df = fetch_ohlcv(symbol, interval="15m", period="5d")
            latest_prices[symbol] = float(df["close"].iloc[-1])
        except Exception as e:
            print(f"Could not fetch current price for {symbol}: {e}")

    for pos in positions:
        symbol = pos["symbol"]
        price = latest_prices.get(symbol)
        if price is None:
            continue

        try:
            take_profit = float(pos["take_profit"])
            stop_loss = float(pos["stop_loss"])
        except (ValueError, KeyError):
            continue

        if price >= take_profit:
            update_position(pos["_row"], "TP_HIT", price, "WIN")
            msg = f"✅ {symbol}: Take-profit tercapai di {price:,.0f} (target {take_profit:,.0f})"
            print(msg)
            if send_notification:
                send_notification(msg)
        elif price <= stop_loss:
            update_position(pos["_row"], "SL_HIT", price, "LOSS")
            msg = f"🛑 {symbol}: Stop-loss kena di {price:,.0f} (batas {stop_loss:,.0f})"
            print(msg)
            if send_notification:
                send_notification(msg)
        # else: still open, nothing to update
