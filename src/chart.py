"""
Generates a 4-panel chart (Candlesticks+EMA, Volume, RSI, MACD) as PNG
image bytes, ready to send via Telegram's sendPhoto endpoint.
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


def generate_chart(symbol: str, df) -> bytes:
    """
    df must already have indicator columns from indicators.add_indicators():
    close, volume, rsi, ema_20, ema_50, MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

    Returns PNG image bytes.
    """
    # Use the last ~60 candles so the chart stays readable
    plot_df = df.tail(60).reset_index(drop=True)

    # Use a sequential index for x instead of real timestamps. Real
    # timestamps create big visual gaps/spikes across the lunch break and
    # overnight/weekend, which makes the line look jagged even though the
    # actual price movement is smooth. Plotting candle-to-candle instead
    # (like TradingView/mplfinance do) fixes that.
    x = range(len(plot_df))
    time_labels = plot_df["open_time"]

    fig, axes = plt.subplots(
        4, 1, figsize=(10, 11), sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1, 1]}
    )
    fig.suptitle(f"{symbol}", fontsize=14, fontweight="bold")

    # --- Panel 1: Candlesticks + EMA ---
    ax_price = axes[0]
    _plot_candlesticks(ax_price, x, plot_df)
    ax_price.plot(x, plot_df["ema_20"], label="EMA 20", color="#ff9800", linewidth=1.2)
    ax_price.plot(x, plot_df["ema_50"], label="EMA 50", color="#2962ff", linewidth=1.2)
    ax_price.set_ylabel("Price")
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.grid(alpha=0.3)

    # --- Panel 2: Volume ---
    ax_vol = axes[1]
    # Color by candle direction (teal up / red down) to match the price panel,
    # full opacity for volume spikes vs average, faded otherwise.
    vol_avg = plot_df["volume_avg_20"]
    vol_colors = []
    for o, c, v, a in zip(plot_df["open"], plot_df["close"], plot_df["volume"], vol_avg.fillna(0)):
        base = "#26a69a" if c >= o else "#ef5350"
        vol_colors.append(base if v > a else base + "80")  # add alpha if not a spike
    ax_vol.bar(x, plot_df["volume"], color=vol_colors, width=0.7)
    ax_vol.set_ylabel("Volume")
    ax_vol.grid(alpha=0.3)

    # --- Panel 3: RSI ---
    ax_rsi = axes[2]
    ax_rsi.plot(x, plot_df["rsi"], color="#9467bd", linewidth=1.2)
    ax_rsi.axhline(70, color="red", linestyle="--", linewidth=0.8)
    ax_rsi.axhline(30, color="green", linestyle="--", linewidth=0.8)
    ax_rsi.set_ylabel("RSI")
    ax_rsi.set_ylim(0, 100)
    ax_rsi.grid(alpha=0.3)

    # --- Panel 4: MACD ---
    ax_macd = axes[3]
    ax_macd.plot(x, plot_df["MACD_12_26_9"], label="MACD", color="#1f77b4", linewidth=1)
    ax_macd.plot(x, plot_df["MACDs_12_26_9"], label="Signal", color="#ff7f0e", linewidth=1)
    hist = plot_df["MACDh_12_26_9"]
    hist_colors = ["#2ca02c" if v >= 0 else "#d62728" for v in hist.fillna(0)]
    ax_macd.bar(x, hist, color=hist_colors, width=0.7)
    ax_macd.set_ylabel("MACD")
    ax_macd.legend(loc="upper left", fontsize=8)
    ax_macd.grid(alpha=0.3)

    # Label a handful of x-ticks with real dates/times instead of every point
    step = max(len(x) // 8, 1)
    tick_positions = list(x)[::step]
    tick_labels = [time_labels.iloc[i].strftime("%m-%d %H:%M") for i in tick_positions]
    ax_macd.set_xticks(tick_positions)
    ax_macd.set_xticklabels(tick_labels, rotation=45, fontsize=8, ha="right")
    ax_macd.set_xlim(-1, len(x))

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
