"""
Generates candlestick charts (Candlesticks+EMA, Volume, RSI, MACD) as PNG
image bytes, ready to send via Telegram's sendPhoto endpoint.

generate_dual_chart() is the main entry point used by main.py: it renders
two timeframes side by side (e.g. 15m and 1D) in a single image so you can
see short-term and longer-term structure at a glance.
"""

import io
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, safe for CI/servers
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def _plot_candlesticks(ax, x, plot_df):
    """Draws OHLC candlesticks at positions x using plot_df's open/high/low/close."""
    width = 0.6
    for xi, (o, h, l, c) in zip(x, zip(plot_df["open"], plot_df["high"],
                                        plot_df["low"], plot_df["close"])):
        is_up = c >= o
        color = "#26a69a" if is_up else "#ef5350"  # teal up / red down

        # Wick (high-low line)
        ax.plot([xi, xi], [l, h], color=color, linewidth=0.8, zorder=2)

        # Body (open-close rectangle)
        body_bottom = min(o, c)
        body_height = abs(c - o)
        if body_height == 0:
            body_height = (h - l) * 0.02 or 0.01  # thin sliver for doji candles
        ax.add_patch(Rectangle(
            (xi - width / 2, body_bottom), width, body_height,
            facecolor=color, edgecolor=color, zorder=3
        ))


def _draw_timeframe_column(axes_col, plot_df, timeframe_label: str, date_fmt: str):
    """
    Draws the 4-panel stack (candlesticks+EMA, volume, RSI, MACD) into one
    column of axes. axes_col is a length-4 array: [ax_price, ax_vol, ax_rsi, ax_macd].
    """
    ax_price, ax_vol, ax_rsi, ax_macd = axes_col

    # Sequential index instead of real timestamps, so gaps (lunch break,
    # overnight, weekends) don't stretch the x-axis and make the chart
    # look jagged. Ticks are relabeled with real dates/times afterward.
    x = range(len(plot_df))
    time_labels = plot_df["open_time"]

    # --- Panel 1: Candlesticks + EMA, with timeframe label as the title ---
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
        vol_colors.append(base if v > a else base + "80")  # faded if not a spike
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

    # Label a handful of x-ticks with real dates/times instead of every point
    step = max(len(x) // 6, 1)
    tick_positions = list(x)[::step]
    tick_labels = [time_labels.iloc[i].strftime(date_fmt) for i in tick_positions]
    ax_macd.set_xticks(tick_positions)
    ax_macd.set_xticklabels(tick_labels, rotation=45, fontsize=7, ha="right")
    ax_macd.set_xlim(-1, len(x))


def generate_dual_chart(symbol: str, df_15m, df_1d,
                         candles_15m: int = 60, candles_1d: int = 60) -> bytes:
    """
    Renders two timeframes side by side in one image: 15-minute chart on
    the left, 1-day chart on the right. Both df_15m and df_1d must already
    have indicator columns from indicators.add_indicators().

    Returns PNG image bytes.
    """
    plot_15m = df_15m.tail(candles_15m).reset_index(drop=True)
    plot_1d = df_1d.tail(candles_1d).reset_index(drop=True)

    fig, axes = plt.subplots(
        4, 2, figsize=(18, 11),
        gridspec_kw={"height_ratios": [3, 1, 1, 1]}
    )
    fig.suptitle(symbol, fontsize=15, fontweight="bold")

    _draw_timeframe_column(axes[:, 0], plot_15m, "15-Minute Chart", "%m-%d %H:%M")
    _draw_timeframe_column(axes[:, 1], plot_1d, "1-Day Chart", "%Y-%m-%d")

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_chart(symbol: str, df, timeframe_label: str = "15-Minute Chart",
                    date_fmt: str = "%m-%d %H:%M") -> bytes:
    """
    Single-timeframe chart (kept for cases where you only want one panel
    set, e.g. testing). Prefer generate_dual_chart() for the normal alert flow.
    """
    plot_df = df.tail(60).reset_index(drop=True)

    fig, axes = plt.subplots(
        4, 1, figsize=(10, 11),
        gridspec_kw={"height_ratios": [3, 1, 1, 1]}
    )
    fig.suptitle(symbol, fontsize=14, fontweight="bold")

    _draw_timeframe_column(axes, plot_df, timeframe_label, date_fmt)

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
