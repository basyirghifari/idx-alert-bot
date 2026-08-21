"""
Main entry point. Loops over your stock watchlist, fetches data via
yfinance, computes indicators, checks alert rules (including RSI
divergence), and sends any triggered alerts to Telegram with a dual
timeframe chart. Designed to run on a schedule during market hours
(see .github/workflows/check.yml).
"""

from fetch_data import fetch_ohlcv
from indicators import add_indicators
from alert_rules import load_state, save_state, check_alerts
from telegram_bot import send_telegram_photo
from chart import generate_dual_chart

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

WATCHLIST = CONGLOMERATE_GROUP_STOCKS + COMMODITY_STOCKS + FMCG_STOCKS

# Alerts (including divergence) are evaluated on the 15-minute timeframe.
INTERVAL = "15m"
PERIOD = "5d"        # must fit yfinance's interval limits, see fetch_data.py

# The daily timeframe is only used for the second chart panel (context),
# not for alert evaluation.
DAILY_INTERVAL = "1d"
DAILY_PERIOD = "6mo"

# How many recent 15m candles the divergence check looks at. Must match
# the candles_15m passed to generate_dual_chart so pivot indices line up
# with what's actually drawn on the chart.
DIVERGENCE_LOOKBACK = 60


def main():
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
                print(f"Sending alert for {symbol}:\n{caption}")

                df_daily = fetch_ohlcv(symbol, interval=DAILY_INTERVAL, period=DAILY_PERIOD)
                df_daily = add_indicators(df_daily)

                chart_bytes = generate_dual_chart(
                    symbol, df, df_daily,
                    candles_15m=DIVERGENCE_LOOKBACK,
                    divergence=divergence,
                )
                send_telegram_photo(chart_bytes, caption=caption)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    if not any_alerts:
        print("No alerts triggered this run.")

    save_state(state)


if __name__ == "__main__":
    main()
