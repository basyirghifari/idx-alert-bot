"""
Sends alert messages/photos to one or more Telegram chats via the Bot API.

Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.

TELEGRAM_CHAT_ID supports MULTIPLE recipients: separate chat IDs with a
comma, e.g. "111111111,222222222,-1009876543210" (a negative ID is a
group chat). Each recipient gets sent to independently — if delivery to
one fails (e.g. they blocked the bot, or haven't messaged it yet), that
failure is logged and the rest still go through rather than the whole
run crashing.
"""

import os
import requests


def _get_chat_ids() -> list:
    chat_id_str = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id_str:
        raise RuntimeError("Missing TELEGRAM_CHAT_ID environment variable.")
    chat_ids = [c.strip() for c in chat_id_str.split(",") if c.strip()]
    if not chat_ids:
        raise RuntimeError("TELEGRAM_CHAT_ID is set but contains no valid chat IDs.")
    return chat_ids


def _get_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable.")
    return token


def send_telegram_message(text: str) -> None:
    token = _get_token()
    chat_ids = _get_chat_ids()
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for chat_id in chat_ids:
        try:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Failed to send Telegram message to chat_id {chat_id}: {e}")


def send_telegram_photo(image_bytes: bytes, caption: str = "") -> None:
    """
    Sends a PNG image (as bytes) to every configured chat with an
    optional caption. Telegram captions are capped at 1024 characters —
    longer captions are truncated here to avoid an API error.
    """
    token = _get_token()
    chat_ids = _get_chat_ids()

    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    for chat_id in chat_ids:
        try:
            # Telegram needs a fresh file object per request — a BytesIO
            # or bytes object already consumed by a prior request won't
            # re-send correctly, so we reconstruct the files dict each time.
            files = {"photo": ("chart.png", image_bytes, "image/png")}
            data = {"chat_id": chat_id, "caption": caption}
            response = requests.post(url, data=data, files=files, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Failed to send Telegram photo to chat_id {chat_id}: {e}")
