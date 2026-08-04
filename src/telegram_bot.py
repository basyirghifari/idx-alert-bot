"""
Sends alert messages to a Telegram chat via the Bot API.
Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
"""

import os
import requests


def send_telegram_message(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables."
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    response = requests.post(url, json=payload, timeout=15)
    response.raise_for_status()


def send_telegram_photo(image_bytes: bytes, caption: str = "") -> None:
    """
    Sends a PNG image (as bytes) to Telegram with an optional caption.
    Telegram captions are capped at 1024 characters — longer captions
    are truncated here to avoid an API error.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables."
        )

    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {"photo": ("chart.png", image_bytes, "image/png")}
    data = {"chat_id": chat_id, "caption": caption}

    response = requests.post(url, data=data, files=files, timeout=30)
    response.raise_for_status()
