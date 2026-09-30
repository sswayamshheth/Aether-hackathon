"""Explainable severity. Every point added to the score is recorded as a reason the
operator can read; nothing is hidden inside a model."""
from __future__ import annotations

BASE = {"accident": 55, "crowd": 45, "baggage": 35}
LEVELS = [(80, "Critical"), (60, "High"), (40, "Medium"), (0, "Low")]


def level(score: float) -> str:
    return next(name for cut, name in LEVELS if score >= cut)


def score_incident(typ: str, subtype: str, confidence: float, duration_s: float,
                   n_cameras: int, details: dict) -> tuple[float, str, list[dict]]:
    """Returns (score 0-100, level, reasons). Each reason is {"text", "points"}."""
    reasons: list[dict] = []

    def add(points: float, text: str) -> None:
        if points:
            reasons.append({"text": text, "points": round(points)})

    add(BASE.get(typ, 30), f"{typ.capitalize()} incident (base score)")
    add(min(20, max(0, (confidence - 0.5) * 40)), f"Detection confidence {confidence:.0%}")

    people = int(details.get("people") or 0)
    vehicles = int(details.get("vehicles") or 0)
    if typ == "accident":
        cls = str(details.get("model_class", "")).lower()
        if "severe" in cls:
            add(15, "Model classed the collision as severe")
        elif "moderate" in cls:
            add(6, "Model classed the collision as moderate")
        if vehicles >= 2:
            add(8, f"{vehicles} vehicles involved")
        if people:
            add(min(12, 6 + 3 * people), f"{people} {'person' if people == 1 else 'people'} at the scene")
        if len(details.get("sources", [])) >= 2:
            add(5, "Model and trajectory rule agree")
        if duration_s >= 10:
            add(8, f"Scene has not cleared for {duration_s:.0f}s")
    elif typ == "crowd":
        if people >= 8:
            add(min(18, people), f"{people} people in view")
        ratio = details.get("motion_ratio")
        if ratio and ratio >= 2:
            add(min(12, 3 * ratio), f"Crowd motion {ratio:.1f}x above this camera's baseline")
        if subtype == "overcrowding":
            add(8, f"Occupancy above the limit of {details.get('limit')}")
        if duration_s >= 8:
            add(8, f"Sustained for {duration_s:.0f}s")
    elif typ == "baggage":
        away = float(details.get("owner_away_s") or 0)
        if subtype == "abandoned":
            add(20, f"Abandoned: {details.get('owner_text', f'owner away {away:.0f}s')}")
        else:
            add(8, f"Unattended: {details.get('owner_text', f'owner away {away:.0f}s')}")
        if away >= 60:
            add(10, "Left for over a minute")
        if details.get("people_nearby"):
            n = int(details["people_nearby"])
            add(min(10, 4 + 2 * n), f"{n} other {'person' if n == 1 else 'people'} close to the object")
        if details.get("zone_kind") == "restricted":
            add(12, f"Inside restricted zone '{details.get('zone')}'")

    if n_cameras >= 2:
        add(min(16, 8 * (n_cameras - 1)), f"Seen by {n_cameras} cameras in the same area")

    total = float(min(100, sum(r["points"] for r in reasons)))
    return total, level(total), reasons
