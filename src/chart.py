"""
Generates a 4-panel chart (Price+EMA, Volume, RSI, MACD) as PNG image
bytes, ready to send via Telegram's sendPhoto endpoint.
"""

import io
import matplotlib
matplotlib.use("Agg")  # non-interactive backend, safe for CI/servers
import matplotlib.pyplot as plt


def generate_chart(symbol: str, df) -> bytes:
    """
    df must already have indicator columns from indicators.add_indicators():
    close, volume, rsi, ema_20, ema_50, MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

    Returns PNG image bytes.
    """
    # Use the last ~60 candles so the chart stays readable
    plot_df = df.tail(60).reset_index(drop=True)
    x = plot_df["open_time"]

    fig, axes = plt.subplots(
        4, 1, figsize=(10, 11), sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1, 1]}
    )
    fig.suptitle(f"{symbol}", fontsize=14, fontweight="bold")

    # --- Panel 1: Price + EMA ---
    ax_price = axes[0]
    ax_price.plot(x, plot_df["close"], label="Close", color="#1f77b4", linewidth=1.5)
    ax_price.plot(x, plot_df["ema_20"], label="EMA 20", color="#ff7f0e", linewidth=1, linestyle="--")
    ax_price.plot(x, plot_df["ema_50"], label="EMA 50", color="#2ca02c", linewidth=1, linestyle="--")
    ax_price.set_ylabel("Price")
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.grid(alpha=0.3)

    # --- Panel 2: Volume ---
    ax_vol = axes[1]
    vol_avg = plot_df["volume_avg_20"]
    colors = ["#d62728" if v > a else "#7f7f7f"
              for v, a in zip(plot_df["volume"], vol_avg.fillna(0))]
    ax_vol.bar(x, plot_df["volume"], color=colors, width=0.03)
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
    ax_macd.bar(x, hist, color=hist_colors, width=0.03)
    ax_macd.set_ylabel("MACD")
    ax_macd.legend(loc="upper left", fontsize=8)
    ax_macd.grid(alpha=0.3)

    # Thin out x-axis labels so they don't overlap
    ax_macd.tick_params(axis="x", rotation=45, labelsize=8)
    step = max(len(x) // 8, 1)
    ax_macd.set_xticks(x[::step])

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
