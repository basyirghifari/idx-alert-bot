"""
Uses an AI provider (Claude or Gemini — pick via AI_PROVIDER in main.py)
to suggest an entry price range, take-profit, and stop-loss for BUY-side
alerts only. This is a technical-analysis-based suggestion generated from
recent price/indicator data — not financial advice, and not guaranteed to
be profitable. Always sanity-check before acting on it.

Requires ONE of these environment variables, matching whichever provider
is selected:
  - ANTHROPIC_API_KEY (for provider="claude")
  - GEMINI_API_KEY    (for provider="gemini")

If the relevant key is missing, or the AI call fails or returns something
unparseable, this falls back to a simple ATR-based calculation so the bot
keeps working either way.
"""

import os
import json
import re

import pandas as pd

CLAUDE_MODEL = "claude-sonnet-4-6"
# Google released gemini-3.7-flash (GA, stable) on 2026-08-13. Model names
# change fairly often — check https://ai.google.dev/gemini-api/docs/models
# if this call starts failing with a "model not found" error.
GEMINI_MODEL = "gemini-3.7-flash"

_claude_client = None
_gemini_client = None


def _get_claude_client():
    global _claude_client
    if _claude_client is None:
        from anthropic import Anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY environment variable.")
        _claude_client = Anthropic(api_key=api_key)
    return _claude_client


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GEMINI_API_KEY environment variable.")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _extract_json(text: str) -> dict:
    """Strips markdown code fences if present, then parses JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _call_claude(prompt: str) -> str:
    client = _get_claude_client()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _call_gemini(prompt: str) -> str:
    from google.genai import types
    client = _get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        # Ask Gemini to return raw JSON directly — skips needing to strip
        # markdown fences, since Gemini honors this constraint reliably.
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return response.text


def _fallback_plan(current_price: float, atr: float) -> dict:
    """
    Simple ATR-based plan used when the AI call isn't available or fails.
    Entry zone = tight band around current price (±0.25 ATR).
    Stop-loss = 1.5 ATR below current price.
    Take-profit = 3 ATR above current price (2:1 reward:risk).
    """
    return {
        "entry_low": round(current_price - 0.25 * atr, 2),
        "entry_high": round(current_price + 0.25 * atr, 2),
        "take_profit": round(current_price + 3 * atr, 2),
        "stop_loss": round(current_price - 1.5 * atr, 2),
        "reasoning": "Fallback plan based on ATR (AI unavailable or failed).",
        "source": "fallback",
    }


def generate_trade_plan(symbol: str, df: pd.DataFrame, signal_messages: list,
                         lookback: int = 15, provider: str = "claude") -> dict:
    """
    df must already have indicator columns from indicators.add_indicators()
    (rsi, ema_20, ema_50, atr, MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9).

    provider: "claude" or "gemini" — which AI to call. Falls back to the
    ATR calculation regardless of provider if the call fails.

    Returns:
    {
        "entry_low": float, "entry_high": float,
        "take_profit": float, "stop_loss": float,
        "reasoning": str,
        "source": "ai" | "fallback",
    }
    """
    latest = df.iloc[-1]
    current_price = float(latest["close"])
    atr_val = latest.get("atr")
    atr = float(atr_val) if pd.notna(atr_val) else current_price * 0.01

    fallback = _fallback_plan(current_price, atr)

    try:
        price_summary = df.tail(lookback)[
            ["open_time", "open", "high", "low", "close", "volume"]
        ].to_string(index=False)

        prompt = f"""You are a technical analysis assistant. A BUY-side signal just triggered for {symbol} on the Indonesia Stock Exchange (IDX).

Signal(s) that triggered: {"; ".join(signal_messages)}

Current price: {current_price}
RSI (14): {latest.get('rsi')}
EMA 20: {latest.get('ema_20')}
EMA 50: {latest.get('ema_50')}
MACD: {latest.get('MACD_12_26_9')}, Signal: {latest.get('MACDs_12_26_9')}, Histogram: {latest.get('MACDh_12_26_9')}
ATR (14): {atr}

Recent candles, most recent last (1-hour timeframe):
{price_summary}

Suggest a BUY trade plan for swing trading: a realistic entry price RANGE (not one exact price), a take-profit level, and a stop-loss level. Base the stop-loss on nearby support and/or ATR. Base the take-profit on a sensible risk:reward ratio (aim for at least 1.5:1).

Respond with ONLY a JSON object, no other text, no markdown fences:
{{"entry_low": <number>, "entry_high": <number>, "take_profit": <number>, "stop_loss": <number>, "reasoning": "<one sentence, under 30 words>"}}"""

        if provider == "gemini":
            text = _call_gemini(prompt)
        elif provider == "claude":
            text = _call_claude(prompt)
        else:
            raise ValueError(f"Unknown AI provider: {provider!r} (use 'claude' or 'gemini')")

        parsed = _extract_json(text)

        required = {"entry_low", "entry_high", "take_profit", "stop_loss", "reasoning"}
        if not required.issubset(parsed.keys()):
            raise ValueError("AI response missing required fields")

        # Basic sanity check: for a buy plan, stop_loss should be below
        # entry and take_profit should be above it. If the AI's numbers
        # don't make sense, fall back rather than log a broken plan.
        if not (parsed["stop_loss"] < parsed["entry_low"] <= parsed["entry_high"] < parsed["take_profit"]):
            raise ValueError(f"AI response failed sanity check: {parsed}")

        parsed["source"] = "ai"
        return parsed

    except Exception as e:
        print(f"AI trade plan generation failed for {symbol} (provider={provider}), using fallback: {e}")
        return fallback
