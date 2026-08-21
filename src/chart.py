"""
Generates candlestick charts (Candlesticks+EMA, Volume, RSI, MACD) as PNG
image bytes, ready to send via Telegram's sendPhoto endpoint.

generate_dual_chart() is the main entry point used by main.py: it renders
two timeframes side by side (e.g. 15m and 1D) in a single image so you can
see short-term and longer-term structure at a glance. It can also draw
divergence pivot lines (from divergence.detect_bullish_divergence) on the
15m column's price and RSI panels, TradingView-style.
"""

import io
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, safe for CI/servers
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

DIVERGENCE_COLORS = {
    "regular_bullish": "#00bcd4",  # cyan
    "hidden_bullish": "#ab47bc",   # purple
}
DIVERGENCE_LABELS = {
    "regular_bullish": "Bullish Div",
    "hidden_bullish": "Hidden Bull Div",
}


def _plot_candlesticks(ax, x, plot_df):
    """Draws OHLC candlesticks at positions x using plot_df's open/high/low/close."""
    width = 0.6
    for xi, (o, h, l, c) in zip(x, zip(plot_df["open"], plot_df["high"],
                                        plot_df["low"], plot_df["close"])):
        is_up = c >= o
        color = "#26a69a" if is_up else "#ef5350"  # teal up / red down

        ax.plot([xi, xi], [l, h], color=color, linewidth=0.8, zorder=2)

        body_bottom = min(o, c)
        body_height = abs(c - o)
        if body_height == 0:
            body_height = (h - l) * 0.02 or 0.01
        ax.add_patch(Rectangle(
            (xi - width / 2, body_bottom), width, body_height,
            facecolor=color, edgecolor=color, zorder=3
        ))


def _draw_divergence_lines(ax_price, ax_rsi, plot_df, divergence: dict):
    """Draws a connecting line between the two pivot points on both the
    price panel (using the 'low' column) and RSI panel, plus a label."""
    i1, i2 = divergence["pivot1_idx"], divergence["pivot2_idx"]
    color = DIVERGENCE_COLORS.get(divergence["type"], "#000000")
    label = DIVERGENCE_LABELS.get(divergence["type"], divergence["type"])

    # Only draw if both pivots are within the currently plotted window
    if i1 >= len(plot_df) or i2 >= len(plot_df):
        return

    ax_price.plot([i1, i2], [divergence["price1"], divergence["price2"]],
                  color=color, linewidth=2, linestyle="-", zorder=5,
                  marker="o", markersize=4)
    # Place the label above the more recent pivot so it doesn't get
    # clipped by the x-axis when the pivot sits near the bottom of the panel.
    ax_price.annotate(label, xy=(i2, divergence["price2"]),
                       xytext=(0, 10), textcoords="offset points",
                       fontsize=8, color=color, fontweight="bold",
                       ha="center")

    ax_rsi.plot([i1, i2], [divergence["ind1"], divergence["ind2"]],
                color=color, linewidth=2, linestyle="-", zorder=5,
                marker="o", markersize=4)


def _draw_timeframe_column(axes_col, plot_df, timeframe_label: str, date_fmt: str,
                            divergence: dict = None):
    """
    Draws the 4-panel stack (candlesticks+EMA, volume, RSI, MACD) into one
    column of axes. axes_col is a length-4 array: [ax_price, ax_vol, ax_rsi, ax_macd].
    """
    ax_price, ax_vol, ax_rsi, ax_macd = axes_col

    x = range(len(plot_df))
    time_labels = plot_df["open_time"]

    # --- Panel 1: Candlesticks + EMA ---
    _plot_candlesticks(ax_price, x, plot_df)
    ax_price.plot(x, plot_df["ema_20"], label="EMA 20", color="#ff9800", linewidth=1.2)
    ax_price.plot(x, plot_df["ema_50"], label="EMA 50", color="#2962ff", linewidth=1.2)
    ax_price.set_title(timeframe_label, fontsize=11, fontweight="bold", loc="left")
    ax_price.set_ylabel("Price")
    ax_price.legend(loc="upper left", fontsize=7)
    ax_price.grid(alpha=0.3)

    # --- Panel 2: Volume ---
    vol_avg = plot_df["volume_avg_20"]
    vol_colors = []
    for o, c, v, a in zip(plot_df["open"], plot_df["close"], plot_df["volume"], vol_avg.fillna(0)):
        base = "#26a69a" if c >= o else "#ef5350"
        vol_colors.append(base if v > a else base + "80")
    ax_vol.bar(x, plot_df["volume"], color=vol_colors, width=0.7)
    ax_vol.set_ylabel("Volume")
    ax_vol.grid(alpha=0.3)

    # --- Panel 3: RSI ---
    ax_rsi.plot(x, plot_df["rsi"], color="#9467bd", linewidth=1.2)
    ax_rsi.axhline(70, color="red", linestyle="--", linewidth=0.8)
    ax_rsi.axhline(30, color="green", linestyle="--", linewidth=0.8)
    ax_rsi.set_ylabel("RSI")
    ax_rsi.set_ylim(0, 100)
    ax_rsi.grid(alpha=0.3)

    # --- Panel 4: MACD ---
    ax_macd.plot(x, plot_df["MACD_12_26_9"], label="MACD", color="#1f77b4", linewidth=1)
    ax_macd.plot(x, plot_df["MACDs_12_26_9"], label="Signal", color="#ff7f0e", linewidth=1)
    hist = plot_df["MACDh_12_26_9"]
    hist_colors = ["#2ca02c" if v >= 0 else "#d62728" for v in hist.fillna(0)]
    ax_macd.bar(x, hist, color=hist_colors, width=0.7)
    ax_macd.set_ylabel("MACD")
    ax_macd.legend(loc="upper left", fontsize=7)
    ax_macd.grid(alpha=0.3)

    # --- Divergence overlay (only drawn when provided) ---
    if divergence is not None:
        _draw_divergence_lines(ax_price, ax_rsi, plot_df, divergence)

    step = max(len(x) // 6, 1)
    tick_positions = list(x)[::step]
    tick_labels = [time_labels.iloc[i].strftime(date_fmt) for i in tick_positions]
    ax_macd.set_xticks(tick_positions)
    ax_macd.set_xticklabels(tick_labels, rotation=45, fontsize=7, ha="right")
    ax_macd.set_xlim(-1, len(x))


def generate_dual_chart(symbol: str, df_15m, df_1d,
                         candles_15m: int = 60, candles_1d: int = 60,
                         divergence: dict = None) -> bytes:
    """
    Renders two timeframes side by side in one image: 15-minute chart on
    the left, 1-day chart on the right. Both df_15m and df_1d must already
    have indicator columns from indicators.add_indicators().

    `divergence`, if provided (from divergence.detect_bullish_divergence
    run against df_15m), is drawn as a connecting line on the 15m column's
    price and RSI panels. Pivot indices in `divergence` must be relative
    to df_15m.tail(candles_15m) — i.e. call detect_bullish_divergence with
    the same lookback as candles_15m.

    Returns PNG image bytes.
    """
    plot_15m = df_15m.tail(candles_15m).reset_index(drop=True)
    plot_1d = df_1d.tail(candles_1d).reset_index(drop=True)

    fig, axes = plt.subplots(
        4, 2, figsize=(18, 11),
        gridspec_kw={"height_ratios": [3, 1, 1, 1]}
    )
    fig.suptitle(symbol, fontsize=15, fontweight="bold")

    _draw_timeframe_column(axes[:, 0], plot_15m, "15-Minute Chart", "%m-%d %H:%M",
                            divergence=divergence)
    _draw_timeframe_column(axes[:, 1], plot_1d, "1-Day Chart", "%Y-%m-%d")

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_chart(symbol: str, df, timeframe_label: str = "15-Minute Chart",
                    date_fmt: str = "%m-%d %H:%M", divergence: dict = None) -> bytes:
    """
    Single-timeframe chart (kept for cases where you only want one panel
    set). Prefer generate_dual_chart() for the normal alert flow.
    """
    plot_df = df.tail(60).reset_index(drop=True)

    fig, axes = plt.subplots(
        4, 1, figsize=(10, 11),
        gridspec_kw={"height_ratios": [3, 1, 1, 1]}
    )
    fig.suptitle(symbol, fontsize=14, fontweight="bold")

    _draw_timeframe_column(axes, plot_df, timeframe_label, date_fmt, divergence=divergence)

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
