# IDX Stock Alert Bot — Free Setup Tutorial

Same architecture as the crypto/US-stock versions, targeted at the
Indonesia Stock Exchange (IDX) via `yfinance`. Checks your watchlist
every 15 min during IDX trading hours and pings Telegram when RSI, MACD,
or volume conditions trigger. Cost: $0.

---

## Step 1: Create your Telegram bot

1. Open Telegram, search **@BotFather**, send `/newbot`, follow the prompts.
2. Save the **bot token**.
3. Message your bot once so it can reply.
4. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`, message the
   bot again, refresh — find `"chat":{"id": ...}` for your **chat ID**.

---

## Step 2: Create the GitHub repo

1. New repo on GitHub, e.g. `idx-alert-bot`.
2. Push these files, keeping the structure:
   ```
   idx-alert-bot/
   ├── .github/workflows/check.yml
   ├── src/
   │   ├── fetch_data.py
   │   ├── indicators.py
   │   ├── alert_rules.py
   │   ├── telegram_bot.py
   │   └── main.py
   ├── state.json
   ├── requirements.txt
   └── README.md
   ```
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/idx-alert-bot.git
   git push -u origin main
   ```

---

## Step 3: Add secrets

**Settings → Secrets and variables → Actions → New repository secret**:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

---

## Step 4: Enable Actions and test

1. **Actions** tab → enable if prompted.
2. Click **IDX Stock Alert Check** → **Run workflow** to test immediately.
3. If IDX is closed when you test, yfinance just returns the last
   completed candle — the bot still runs fine, it just won't be "live"
   until market hours.

---

## Step 5: Customize your watchlist

IDX tickers on Yahoo Finance need a **`.JK` suffix**. The default list:

| Ticker | Company |
|---|---|
| `BBCA.JK` | Bank Central Asia |
| `BBRI.JK` | Bank Rakyat Indonesia |
| `TLKM.JK` | Telkom Indonesia |
| `ASII.JK` | Astra International |
| `BMRI.JK` | Bank Mandiri |

Edit `WATCHLIST` in `src/main.py` — add any IDX ticker with `.JK`
appended (e.g. `"UNVR.JK"` for Unilever Indonesia, `"GOTO.JK"` for GoTo).
You can look up tickers on [finance.yahoo.com](https://finance.yahoo.com)
by searching the company name — Yahoo will show the `.JK` symbol.

---

## About IDX trading hours

IDX trades in two sessions, WIB (Western Indonesia Time, UTC+7, **no
daylight saving** — so unlike the US bot, this schedule never needs
adjusting):

| Day | Session 1 | Session 2 |
|---|---|---|
| Mon–Thu | 09:00–12:00 WIB | 13:30–15:49 WIB |
| Fri | 09:00–11:30 WIB | 14:00–15:49 WIB |

The workflow cron (`*/15 2-8 * * 1-5`) runs every 15 min from 02:00–08:59
UTC (= 09:00–15:59 WIB), which spans both sessions plus the lunch break.
It'll fire a few extra no-op checks during the midday break, which is
harmless — the dedup logic in `state.json` just returns "no alerts" then.

**Note:** this doesn't account for IDX public holidays (Idul Fitri,
Independence Day, etc.) — the workflow will still run on those days but
yfinance will just return stale data, which won't trigger duplicate
alerts thanks to the state tracking.

---

## Known limitations (free tier)

- Yahoo Finance's data for IDX tickers can be a bit less complete than
  for US large-caps — very small-cap/illiquid stocks may have gaps.
- Yahoo's API (which yfinance wraps) is unofficial — if a run suddenly
  fails, check the yfinance GitHub issues page.
- GitHub Actions cron can run a few minutes late under load.

---

## Next steps / expansion ideas

- Add IDX-specific fundamentals (many local screeners like Stockbit/RTI
  have free tiers you could integrate via web scraping if needed).
- Track IDR/USD alongside your stock alerts for currency context.
- Add ARA/ARB (auto-reject) proximity alerts — IDX has daily price-move
  limits, which is a distinctly local rule worth encoding as a custom
  alert condition in `alert_rules.py`.
