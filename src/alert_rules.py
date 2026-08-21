"""
Defines alert conditions and prevents duplicate/spammy alerts
by tracking the last-known state per symbol in state.json.
"""

import json
from pathlib import Path
import pandas as pd

from divergence import detect_bullish_divergence

STATE_FILE = Path(__file__).resolve().parent.parent / "state.json"


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def check_alerts(symbol: str, df: pd.DataFrame, state: dict):
    """
    Looks at the latest row of indicator data and returns:
      (messages, divergence)
    - messages: list of human-readable alert strings to send
    - divergence: the divergence dict from detect_bullish_divergence(),
      or None — passed along so the chart can draw the pivot lines
    Updates `state` in place so we don't re-alert every run.
    """
    messages = []
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    sym_state = state.get(symbol, {})

    # --- RSI oversold / overbought ---
    rsi = latest["rsi"]
    if rsi is not None and not pd.isna(rsi):
        if rsi < 30 and sym_state.get("rsi_zone") != "oversold":
            messages.append(f"📉 {symbol}: RSI oversold ({rsi:.1f}) — potential bounce zone")
            sym_state["rsi_zone"] = "oversold"
        elif rsi > 70 and sym_state.get("rsi_zone") != "overbought":
            messages.append(f"📈 {symbol}: RSI overbought ({rsi:.1f}) — potential pullback zone")
            sym_state["rsi_zone"] = "overbought"
        elif 30 <= rsi <= 70:
            sym_state["rsi_zone"] = "neutral"

    # --- MACD bullish/bearish crossover ---
    macd_col, signal_col = "MACD_12_26_9", "MACDs_12_26_9"
    if macd_col in df.columns and signal_col in df.columns:
        macd_now, signal_now = latest[macd_col], latest[signal_col]
        macd_prev, signal_prev = prev[macd_col], prev[signal_col]
        if pd.notna(macd_now) and pd.notna(macd_prev):
            crossed_up = macd_prev < signal_prev and macd_now > signal_now
            crossed_down = macd_prev > signal_prev and macd_now < signal_now
            if crossed_up:
                messages.append(f"🟢 {symbol}: MACD bullish crossover")
            elif crossed_down:
                messages.append(f"🔴 {symbol}: MACD bearish crossover")

    # --- Volume spike ---
    vol, vol_avg = latest["volume"], latest["volume_avg_20"]
    if pd.notna(vol_avg) and vol_avg > 0 and vol > 2 * vol_avg:
        messages.append(f"🔊 {symbol}: Volume spike — {vol:,.0f} vs avg {vol_avg:,.0f}")

    # --- RSI divergence (regular bullish + hidden bullish) ---
    divergence = detect_bullish_divergence(df, indicator_col="rsi", price_col="low",
                                            order=3, lookback=60)
    if divergence:
        # Use the pivot's actual timestamp as the dedup key, since candle
        # positions shift every run as new candles arrive.
        recent_times = df.tail(60).reset_index(drop=True)["open_time"]
        pivot_time = str(recent_times.iloc[divergence["pivot2_idx"]])
        state_key = f"divergence_{divergence['type']}"

        if sym_state.get(state_key) != pivot_time:
            sym_state[state_key] = pivot_time
            if divergence["type"] == "regular_bullish":
                messages.append(
                    f"🟢🔀 {symbol}: Bullish Divergence (price lower low, RSI higher low) — possible reversal"
                )
            else:  # hidden_bullish
                messages.append(
                    f"🟩🔁 {symbol}: Hidden Bullish Divergence (price higher low, RSI lower low) — uptrend likely continuing"
                )

    state[symbol] = sym_state
    return messages, divergence
