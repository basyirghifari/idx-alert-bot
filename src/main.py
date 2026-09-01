"""
Main entry point. Loops over your stock watchlist, fetches data via
yfinance, computes indicators, checks alert rules (including RSI
divergence), and sends any triggered alerts to Telegram with a dual
timeframe chart. For BUY-side signals, also asks the Claude API for a
suggested entry range / take-profit / stop-loss, logs the call to
Google Sheets, and — at the start of each run — checks any previously
logged OPEN positions to see if they've hit TP or SL yet.

Designed to run on a schedule during market hours (see
.github/workflows/check.yml).
"""

from fetch_data import fetch_ohlcv
from indicators import add_indicators
from alert_rules import load_state, save_state, check_alerts
from telegram_bot import send_telegram_photo, send_telegram_message
from chart import generate_dual_chart
from ai_analysis import generate_trade_plan
import google_sheets
import position_tracker

# Edit this list to whatever IDX tickers you want to track.
# Yahoo Finance uses the ".JK" suffix for Indonesia Stock Exchange listings.
#
# Organized by category. Duplicates across categories are kept out —
# each ticker appears once even if it could arguably fit more than one
# group (e.g. BRPT is both a conglomerate flagship and a commodity/
# petrochemical play).

CONGLOMERATE_GROUP_STOCKS = [
    "ASII.JK",   # Astra International — Astra Group flagship (auto, agri, mining, finance)
    "BBCA.JK",   # Bank Central Asia — Hartono/Djarum family
    "BRPT.JK",   # Barito Pacific — Prajogo Pangestu group holding
    "TPIA.JK",   # Chandra Asri Pacific — Barito/Prajogo group, petrochemicals
    "BNBR.JK",   # Bakrie & Brothers — Bakrie Group holding
    "LPKR.JK",   # Lippo Karawaci — Lippo Group
    "BHIT.JK",   # MNC Investama — MNC Group holding
    "PNLF.JK",   # Panin Financial — Panin Group
    "MEGA.JK",   # Bank Mega — CT Corp
    "SMAR.JK",   # SMART Tbk — Sinar Mas Group (agribusiness/CPO)
]

COMMODITY_STOCKS = [
    "ADRO.JK",   # Adaro Energy — coal
    "PTBA.JK",   # Bukit Asam — coal
    "ITMG.JK",   # Indo Tambangraya Megah — coal
    "INCO.JK",   # Vale Indonesia — nickel
    "ANTM.JK",   # Aneka Tambang — gold & nickel
    "MDKA.JK",   # Merdeka Copper Gold
    "TINS.JK",   # Timah — tin
    "AALI.JK",   # Astra Agro Lestari — palm oil (CPO)
    "LSIP.JK",   # PP London Sumatra — palm oil (CPO)
    "PGAS.JK",   # Perusahaan Gas Negara — natural gas
    "MEDC.JK",   # Medco Energi — oil & gas
]

FMCG_STOCKS = [
    "UNVR.JK",   # Unilever Indonesia
    "ICBP.JK",   # Indofood CBP Sukses Makmur
    "MYOR.JK",   # Mayora Indah
    "GGRM.JK",   # Gudang Garam — tobacco
    "HMSP.JK",   # HM Sampoerna — tobacco
    "KLBF.JK",   # Kalbe Farma — pharma/consumer health
    "CPIN.JK",   # Charoen Pokphand Indonesia — poultry/food
]

# Bakrie Group ecosystem. BNBR (the group's holding company) is already
# tracked under CONGLOMERATE_GROUP_STOCKS above, so it's not repeated
# here to avoid a duplicate in WATCHLIST.
BAKRIE_GROUP_STOCKS = [
    "BUMI.JK",   # Bumi Resources — coal mining
    "BRMS.JK",   # Bumi Resources Minerals — mineral & gold mining
    "ENRG.JK",   # Energi Mega Persada — oil & gas exploration
    "UNSP.JK",   # Bakrie Sumatera Plantations — palm oil & rubber
    "ELTY.JK",   # Bakrieland Development — property/real estate
    "DEWA.JK",   # Darma Henwa — mining contractor services
    "BTEL.JK",   # Bakrie Telecom — telecommunications
    "VIVA.JK",   # Visi Media Asia — media & broadcasting (TVOne, ANTV)
    "MDIA.JK",   # Intermedia Capital — media, VIVA-linked entity
    "VKTR.JK",   # VKTR Teknologi Mobilitas — electric vehicles
    "JGLE.JK",   # Graha Andrasentra Propertindo — property (Jungleland)
]

# Prajogo Pangestu / Barito Group ecosystem. BRPT and TPIA (the group's
# core holding and petrochemical flagship) are already tracked under
# CONGLOMERATE_GROUP_STOCKS above, so they're not repeated here.
PRAJOGO_PANGESTU_STOCKS = [
    "BREN.JK",   # Barito Renewables Energy — geothermal renewable energy
    "CUAN.JK",   # Petrindo Jaya Kreasi — coal & gold mining
    "PTRO.JK",   # Petrosea — mining contractor & engineering services
    "CDIA.JK",   # Chandra Daya Investasi — energy infrastructure & logistics
    "GZCO.JK",   # Gozco Plantations — palm oil (partial Prajogo ownership)
]

# Salim Group ecosystem (Anthoni Salim). ICBP (FMCG), LSIP (palm oil),
# BUMI (coal, strategic affiliate stake), and MEDC (oil & gas, affiliate
# stake) are already tracked elsewhere above, so not repeated here.
SALIM_GROUP_STOCKS = [
    "INDF.JK",   # Indofood Sukses Makmur — parent, instant noodles & food
    "SIMP.JK",   # Salim Ivomas Pratama — agribusiness, Bimoli cooking oil
    "DNET.JK",   # Indoritel Makmur Internasional — holds stakes in Indomaret, FAST, ROTI
    "IMAS.JK",   # Indomobil Sukses Internasional — automotive & vehicle distribution
    "IMJS.JK",   # Indomobil Multi Jasa — vehicle finance & leasing services
    "BINA.JK",   # Bank Ina Perdana — banking
    "DCII.JK",   # DCI Indonesia — data center provider
    "AMMN.JK",   # Amman Mineral Internasional — gold & copper mining (affiliate stake)
]

# Saratoga Group ecosystem (Sandiaga Uno & Edwin Soeryadjaya's investment
# vehicle). MDKA and ADRO (gold/copper mining and coal/energy, both
# Saratoga portfolio companies) are already tracked under
# COMMODITY_STOCKS above, so not repeated here.
SARATOGA_GROUP_STOCKS = [
    "SRTG.JK",   # Saratoga Investama Sedaya — the investment holding company itself
    "MBMA.JK",   # Merdeka Battery Materials — nickel & EV battery ecosystem
    "TBIG.JK",   # Tower Bersama Infrastructure — telecom tower infrastructure
    "MPMX.JK",   # Mitra Pinasthika Mustika — automotive, transport & finance
    "MUTU.JK",   # Mutuagung Lestari — testing/inspection/certification (TIC), Sandiaga entered via private placement 2026
    "PALM.JK",   # Provident Investasi Bersama (formerly Provident Agro) — agribusiness/CPO
]

WATCHLIST = CONGLOMERATE_GROUP_STOCKS + COMMODITY_STOCKS + FMCG_STOCKS + BAKRIE_GROUP_STOCKS + PRAJOGO_PANGESTU_STOCKS + SALIM_GROUP_STOCKS + SARATOGA_GROUP_STOCKS

# Alerts (including divergence) are evaluated on the 1-hour timeframe —
# better suited for swing trading than 15m, since it filters out a lot
# of intraday noise while still updating several times per session.
# yfinance supports "1h" natively, so no resampling is needed.
INTERVAL = "1h"
PERIOD = "3mo"       # must fit yfinance's interval limits, see fetch_data.py
                      # (1h data is available for up to 730 days)

CHART_LABEL = "1-Hour Chart"
CHART_DATE_FMT = "%m-%d %H:%M"

# The daily timeframe is only used for the second chart panel (context),
# not for alert evaluation.
DAILY_INTERVAL = "1d"
DAILY_PERIOD = "6mo"

# How many recent 1h candles the divergence check looks at. Must match
# the candles_15m passed to generate_dual_chart so pivot indices line up
# with what's actually drawn on the chart. 60 hourly candles covers
# roughly the last 2-3 trading weeks for IDX (session ≈ 5.3h/day).
DIVERGENCE_LOOKBACK = 60

# Only these signal types count as a BUY-side call that gets an AI
# entry/TP/SL plan and gets logged to Google Sheets. MACD bearish
# crossover, RSI overbought, and a plain volume spike are excluded —
# they're either sell-side or direction-neutral signals.
BUY_SIGNAL_KEYWORDS = [
    "RSI oversold",
    "MACD bullish crossover",
    "Bullish Divergence",
    "Hidden Bullish Divergence",
]

# Which AI provider generates the entry/TP/SL plan: "claude" or "gemini".
# Switching requires the matching API key secret (ANTHROPIC_API_KEY or
# GEMINI_API_KEY) to be set — see README. If the key is missing or the
# call fails, it automatically falls back to the ATR-based calculation
# regardless of which provider is selected here.
AI_PROVIDER = "gemini"


def is_buy_signal(message: str) -> bool:
    return any(keyword in message for keyword in BUY_SIGNAL_KEYWORDS)


def main():
    # --- Step 1: check any previously logged OPEN positions for TP/SL hits ---
    try:
        position_tracker.check_open_positions(send_notification=send_telegram_message)
    except Exception as e:
        print(f"Position tracking skipped due to error: {e}")

    # --- Step 2: evaluate new alerts as usual ---
    state = load_state()
    any_alerts = False

    for symbol in WATCHLIST:
        try:
            df = fetch_ohlcv(symbol, interval=INTERVAL, period=PERIOD)
            df = add_indicators(df)
            messages, divergence = check_alerts(symbol, df, state)

            if messages:
                any_alerts = True
                caption = "\n".join(messages)

                # --- BUY-side signals get an AI trade plan + Sheets log ---
                buy_messages = [m for m in messages if is_buy_signal(m)]
                if buy_messages:
                    try:
                        plan = generate_trade_plan(symbol, df, buy_messages, provider=AI_PROVIDER)
                        caption += (
                            f"\n\n📋 Trade Plan ({plan['source']}):\n"
                            f"Entry: {plan['entry_low']:,.0f} – {plan['entry_high']:,.0f}\n"
                            f"TP: {plan['take_profit']:,.0f}\n"
                            f"SL: {plan['stop_loss']:,.0f}\n"
                            f"{plan['reasoning']}"
                        )
                        try:
                            google_sheets.append_trade(
                                symbol=symbol,
                                signal="; ".join(buy_messages),
                                entry_low=plan["entry_low"],
                                entry_high=plan["entry_high"],
                                take_profit=plan["take_profit"],
                                stop_loss=plan["stop_loss"],
                                notes=plan["reasoning"],
                            )
                        except Exception as e:
                            print(f"Could not log trade to Google Sheets for {symbol}: {e}")
                    except Exception as e:
                        print(f"AI trade plan step failed for {symbol}: {e}")

                print(f"Sending alert for {symbol}:\n{caption}")

                df_daily = fetch_ohlcv(symbol, interval=DAILY_INTERVAL, period=DAILY_PERIOD)
                df_daily = add_indicators(df_daily)

                chart_bytes = generate_dual_chart(
                    symbol, df, df_daily,
                    candles_15m=DIVERGENCE_LOOKBACK,
                    divergence=divergence,
                    left_label=CHART_LABEL,
                    left_date_fmt=CHART_DATE_FMT,
                )
                send_telegram_photo(chart_bytes, caption=caption)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    if not any_alerts:
        print("No alerts triggered this run.")

    save_state(state)


if __name__ == "__main__":
    main()
