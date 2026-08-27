"""
Logs each BUY trade call to a Google Sheet and lets other modules read
back open positions / update their status.

Requires two environment variables:
  - GOOGLE_SHEET_ID: the spreadsheet ID (the long string in its URL,
    between /d/ and /edit)
  - GOOGLE_SERVICE_ACCOUNT_JSON: the full contents of a Google Cloud
    service account JSON key, as a single string

Setup (see README for full walkthrough):
  1. Create a Google Cloud service account, enable the Sheets API for it,
     and download its JSON key.
  2. Share your target Google Sheet with the service account's email
     (the "client_email" field inside the JSON) as an Editor.
  3. Paste the Sheet ID and the full JSON key contents into the two
     GitHub secrets above.

If these two variables aren't set, every function here raises — main.py
catches that and just skips logging for that run rather than crashing.
"""

import os
import json
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
WORKSHEET_NAME = "Trades"
HEADERS = [
    "timestamp", "symbol", "signal", "entry_low", "entry_high",
    "take_profit", "stop_loss", "status", "exit_price", "result", "notes",
]

_client = None


def _get_client():
    global _client
    if _client is None:
        creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not creds_json:
            raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable.")
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def _get_worksheet():
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise RuntimeError("Missing GOOGLE_SHEET_ID environment variable.")

    client = _get_client()
    spreadsheet = client.open_by_key(sheet_id)

    try:
        ws = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS)

    return ws


def append_trade(symbol: str, signal: str, entry_low: float, entry_high: float,
                  take_profit: float, stop_loss: float, notes: str = "") -> None:
    """Logs a new BUY call with status OPEN."""
    ws = _get_worksheet()
    row = [
        datetime.now(timezone.utc).isoformat(),
        symbol, signal, entry_low, entry_high, take_profit, stop_loss,
        "OPEN", "", "", notes,
    ]
    ws.append_row(row)


def get_open_positions() -> list:
    """
    Returns a list of dicts (one per OPEN row), each including '_row'
    (the 1-based sheet row number) so it can be passed to update_position().
    """
    ws = _get_worksheet()
    records = ws.get_all_records()
    open_positions = []
    for i, rec in enumerate(records):
        if str(rec.get("status", "")).upper() == "OPEN":
            rec["_row"] = i + 2  # +1 for the header row, +1 for 1-based indexing
            open_positions.append(rec)
    return open_positions


def update_position(row: int, status: str, exit_price: float, result: str) -> None:
    """Updates an existing row's status/exit_price/result columns."""
    ws = _get_worksheet()
    ws.update_cell(row, HEADERS.index("status") + 1, status)
    ws.update_cell(row, HEADERS.index("exit_price") + 1, exit_price)
    ws.update_cell(row, HEADERS.index("result") + 1, result)
