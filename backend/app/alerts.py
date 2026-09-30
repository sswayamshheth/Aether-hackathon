"""Outbound alerts beyond the dashboard WebSocket.

Telegram is off unless TELEGRAM_ENABLED=1 and a bot token and chat id are set in .env.
Failures are logged and never block the pipeline.
"""
from __future__ import annotations

import logging
import threading

from . import config

log = logging.getLogger("drishti.alerts")
_store = None
_sent: set[tuple[int, str]] = set()


def configure(store) -> None:
    global _store
    _store = store


def _telegram(inc: dict) -> None:
    import httpx

    cams = ", ".join(c["name"] for c in inc.get("cameras") or [])
    reasons = "\n".join(f"- {r['text']}" for r in (inc.get("reasons") or [])[:5])
    text = (f"[{inc['severity']}] {inc['type'].capitalize()} ({inc.get('subtype') or 'n/a'})\n"
            f"Area: {inc.get('area')}\nCameras: {cams}\nScore: {inc['score']:.0f}/100\n{reasons}")
    try:
        r = httpx.post(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                       json={"chat_id": config.TELEGRAM_CHAT, "text": text}, timeout=8)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        log.warning("telegram alert failed: %s", type(e).__name__)


def dispatch(inc: dict) -> None:
    """Called for new incidents and for escalations to High / Critical."""
    key = (inc["id"], inc["severity"])
    if key in _sent:
        return
    _sent.add(key)
    if config.TELEGRAM_ENABLED and config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT:
        threading.Thread(target=_telegram, args=(inc,), daemon=True).start()
