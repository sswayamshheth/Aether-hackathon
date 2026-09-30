"""Optional second opinion on an incident from a vision model (Claude).

Off by default. Runs only when VISION_VERIFY_ENABLED=1 and ANTHROPIC_API_KEY is set in .env.
When it runs: 3 frames from the evidence buffer are sent with head regions blurred, the
model returns strict JSON, and the verdict is stored on the incident. One call per
incident (the stored verdict is the cache). Any failure, timeout or refusal is recorded as
"unavailable" and the pipeline carries on without it.

This path has not been exercised against the live API: no key was available at build time.
"""
from __future__ import annotations

import base64
import logging
import threading
import time

import cv2
import numpy as np

from . import config

log = logging.getLogger("drishti.verify")

SCHEMA = {
    "type": "object",
    "properties": {
        "confirmed": {"type": "boolean"},
        "type": {"type": "string", "enum": ["accident", "crowd", "baggage", "none"]},
        "severity": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "description": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["confirmed", "type", "severity", "description", "reason"],
    "additionalProperties": False,
}

PROMPT = """These are {n} consecutive frames from one fixed CCTV camera, oldest first. \
Coloured boxes and labels were drawn by an automated detector; faces are blurred on purpose.

The detector raised this incident: {title}.
Its reasons: {reasons}

Decide from the frames alone whether that incident is really happening. Be sceptical: \
the detector is often wrong on low-resolution footage, and a box labelled as an incident \
is a claim, not evidence.

Answer with:
- confirmed: true only if the frames themselves show it
- type: accident, crowd, baggage, or none if nothing of the kind is visible
- severity: 1 (minor) to 5 (life-threatening), your own judgement
- description: one line saying what is visible
- reason: one line saying what in the frames led to your answer"""


def enabled() -> bool:
    return config.VISION_VERIFY_ENABLED and bool(config.ANTHROPIC_API_KEY)


def blur_heads(jpeg: bytes, person_boxes: list[tuple[float, float, float, float]]) -> bytes:
    """Blur the top third of every person box before a frame leaves the machine."""
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    for x1, y1, x2, y2 in person_boxes:
        x1, x2 = max(0, int(x1)), min(w, int(x2))
        y1 = max(0, int(y1))
        y2 = min(h, int(y1 + (y2 - y1) * 0.34))
        if x2 - x1 > 2 and y2 - y1 > 2:
            k = max(9, ((x2 - x1) // 2) | 1)
            img[y1:y2, x1:x2] = cv2.GaussianBlur(img[y1:y2, x1:x2], (k, k), 0)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


def _call(frames: list[bytes], inc: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=25.0, max_retries=1)
    content: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                     "data": base64.standard_b64encode(f).decode("ascii")}}
        for f in frames]
    title = f"{inc['type']} ({inc.get('subtype') or 'unspecified'}), severity {inc['severity']}"
    reasons = "; ".join(r["text"] for r in inc.get("reasons") or []) or "none recorded"
    content.append({"type": "text", "text": PROMPT.format(n=len(frames), title=title, reasons=reasons)})
    try:
        # server-side fallback: if the model declines, the API reruns the request on a
        # fallback model inside the same call
        resp = client.beta.messages.create(
            model=config.VISION_MODEL, max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": content}])
    except anthropic.AuthenticationError:
        return {"status": "unavailable", "error": "API key rejected"}
    except anthropic.RateLimitError:
        return {"status": "unavailable", "error": "rate limited"}
    except anthropic.APIStatusError as e:
        return {"status": "unavailable", "error": f"API error {e.status_code}"}
    except anthropic.APIConnectionError:
        return {"status": "unavailable", "error": "no connection or timeout"}
    if resp.stop_reason == "refusal":
        return {"status": "unavailable", "error": "model declined the request"}
    if resp.stop_reason == "max_tokens":
        return {"status": "unavailable", "error": "answer was cut off"}
    import json

    text = next((b.text for b in resp.content if b.type == "text"), "")
    verdict = json.loads(text)
    return {"status": "done", "model": resp.model, **verdict}


def verify_async(store, broadcast, iid: int, frames: list[tuple[bytes, list]]) -> None:
    """frames: (jpeg, person boxes in that jpeg's pixel coordinates), oldest first."""
    if not enabled() or not frames:
        return

    def run() -> None:
        inc = store.incident(iid)
        if not inc or inc.get("verification"):
            return  # already verified: the stored verdict is the cache
        t0 = time.time()
        try:
            verdict = _call([blur_heads(j, boxes) for j, boxes in frames], inc)
        except Exception as e:  # noqa: BLE001  any failure falls back to "no verdict"
            log.warning("vision verification failed: %s", type(e).__name__)
            verdict = {"status": "unavailable", "error": type(e).__name__}
        verdict["seconds"] = round(time.time() - t0, 1)
        timeline = (inc.get("timeline") or [])
        if verdict["status"] == "done":
            word = "confirmed" if verdict["confirmed"] else "did not confirm"
            timeline = timeline + [{"t": time.time(), "text": f"Vision model {word}: {verdict['description']}"}]
        store.update_incident(iid, verification=verdict, timeline=timeline)
        broadcast({"type": "incident.update", "incident": store.incident(iid), "alert": False})

    threading.Thread(target=run, daemon=True, name=f"verify-{iid}").start()
