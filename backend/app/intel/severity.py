"""Explainable severity. Every point added to the score is recorded as a reason the
operator can read; nothing is hidden inside a model."""
from __future__ import annotations

BASE = {"accident": 55, "crowd": 45, "baggage": 35, "fire": 60, "weapon": 65, "violence": 55,
        "medical": 50, "hazard": 45, "security": 30}
TYPE_NAME = {"accident": "Accident", "crowd": "Crowd", "baggage": "Baggage", "fire": "Fire", "weapon": "Weapon",
             "violence": "Violence", "medical": "Medical", "hazard": "Hazard", "security": "Security"}
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

    add(BASE.get(typ, 30), f"{TYPE_NAME.get(typ, typ.capitalize())} incident (base score)")
    ver = details.get("verifier")
    if ver:
        why = ", ".join(t["feature"] for t in ver["top"][:2] if t["effect"] > 0)
        add(min(20, max(0, (ver["p"] - 0.5) * 40)),
            f"ML verifier: {ver['p']:.0%} likely real" + (f" (mostly {why})" if why else ""))
    else:
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

    elif typ == "fire":
        if subtype == "explosion":
            add(15, "Looks like an explosion")
        area = float(details.get("area_pct") or 0)
        if area >= 2:
            add(min(15, area), f"Fire or smoke covers {area:.0f}% of the view")
        if people:
            add(min(12, 4 + 2 * people), f"{people} {'person' if people == 1 else 'people'} nearby")
        if duration_s >= 10:
            add(8, f"Still burning after {duration_s:.0f}s")
    elif typ == "weapon":
        if details.get("held_by_person"):
            add(12, f"A {details.get('object', 'weapon')} held by a person")
        if people >= 2:
            add(min(10, 2 * people), f"{people} people in view")
    elif typ == "violence":
        if subtype == "robbery":
            add(12, "Looks like a robbery")
        if details.get("weapon_seen"):
            add(15, "A weapon was seen during it")
        if people >= 3:
            add(min(10, 2 * people), f"{people} people involved or nearby")
        if duration_s >= 8:
            add(8, f"Going on for {duration_s:.0f}s")
    elif typ == "medical":
        still = float(details.get("lying_still_s") or 0)
        if subtype == "collapse":
            add(15, f"Person lying still for {still:.0f}s")
        elif still >= 3:
            add(6, f"Person on the ground for {still:.0f}s")
    elif typ == "hazard":
        add(0, "")
        if duration_s >= 10:
            add(6, f"Visible for {duration_s:.0f}s")
    elif typ == "security":
        if subtype == "intrusion":
            add(15, f"Person inside restricted zone '{details.get('zone')}'")
        elif subtype == "wrong-way driving":
            add(20, f"Vehicle driving against traffic in '{details.get('zone')}'")
        elif subtype == "pedestrian on road":
            add(10, f"Pedestrian in lane '{details.get('zone')}'")
        elif subtype == "stalled vehicle":
            add(8, f"Vehicle stopped for {details.get('stopped_s')}s in '{details.get('zone')}'")
        elif subtype == "loitering":
            add(4, f"Same person in one spot for {details.get('present_s')}s")

    if n_cameras >= 2:
        add(min(16, 8 * (n_cameras - 1)), f"Seen by {n_cameras} cameras in the same area")

    total = float(min(100, sum(r["points"] for r in reasons)))
    return total, level(total), reasons
