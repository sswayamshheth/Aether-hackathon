"""ML verifier: the learned layer on top of the rule engines.

For each incident type, the engine's rules propose candidates and attach a `features`
dict. A candidate group (one ongoing event on one camera) is summarised into a fixed
feature vector (mean and max of each feature, plus how many hits and for how long), and a
per-type logistic regression, trained on labelled footage by training/train_verifiers.py,
gives the probability that the event is real.

Logistic regression was chosen over boosted trees on purpose: with a few hundred training
events it is harder to overfit, and every decision decomposes exactly into per-feature
contributions (weight x standardised value), which the dashboard shows as the reasons.

Models are stored as JSON (models/verifiers.json), not pickles, so loading one cannot run
code. A type with no trained model falls back to the rule gate in filter.py.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from .. import config

log = logging.getLogger("drishti.verifier")
PATH = config.MODELS / "verifiers.json"

LABELS = {
    # readable names for the contribution list
    "violence_p": "violence model score", "people": "people in view", "closest_pair": "distance between people",
    "speed_max": "fastest person", "speed_mean": "average movement", "scene_fight": "scene looks like a fight",
    "scene_robbery": "scene looks like a robbery", "weapon_seen": "weapon seen", "fire_conf": "fire detector score",
    "smoke_conf": "smoke detector score", "area": "size of fire/smoke", "growth": "fire/smoke growing",
    "boxes": "number of detections", "scene_fire": "scene looks like fire", "scene_smoke": "scene looks like smoke",
    "scene_explosion": "scene looks like an explosion", "weapon_conf": "weapon detector score",
    "held": "weapon held by a person", "fallen_conf": "fall detector score", "fallen_boxes": "fallen people",
    "lying_still_s": "time lying still", "scene_collapse": "scene looks like a collapse",
    "model_conf": "accident model score", "rule": "trajectory rule fired", "vehicles": "vehicles involved",
    "scene_crash": "scene looks like a crash", "hits": "repeat detections", "duration": "duration",
    "crowd_p": "crowd model score", "motion_ratio": "motion vs baseline",
}


def summarise(feature_list: list[dict], duration: float) -> dict[str, float]:
    """Group-level features from the per-candidate feature dicts."""
    keys = sorted({k for f in feature_list for k in f})
    out: dict[str, float] = {"hits": float(len(feature_list)), "duration": float(duration)}
    for k in keys:
        vals = [float(f[k]) for f in feature_list if k in f and f[k] is not None]
        if vals:
            out[f"{k}__mean"] = sum(vals) / len(vals)
            out[f"{k}__max"] = max(vals)
    return out


def readable(name: str) -> str:
    base, _, agg = name.partition("__")
    label = LABELS.get(base, base.replace("_", " "))
    return f"{label} ({'peak' if agg == 'max' else 'average'})" if agg else label


class Verifier:
    def __init__(self, path: Path = PATH) -> None:
        self.models: dict[str, dict] = {}
        if path.exists():
            try:
                self.models = json.loads(path.read_text())["types"]
                log.info("verifiers loaded for %s", sorted(self.models))
            except Exception:  # noqa: BLE001
                log.exception("could not read %s; using rule gates only", path)

    def has(self, typ: str) -> bool:
        return typ in self.models

    def threshold(self, typ: str) -> float:
        return self.models[typ]["threshold"]

    def score(self, typ: str, feats: dict[str, float]) -> tuple[float, list[tuple[str, float]]]:
        """Probability the event is real, and each feature's contribution to the log-odds."""
        m = self.models[typ]
        z = m["intercept"]
        contrib = []
        for name, mu, sd, w in zip(m["features"], m["mean"], m["std"], m["coef"]):
            x = feats.get(name, mu)  # a feature the engine did not produce counts as average
            c = w * (x - mu) / (sd or 1.0)
            z += c
            contrib.append((name, c))
        p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
        contrib.sort(key=lambda t: -abs(t[1]))
        return p, contrib


_verifier: Verifier | None = None


def get_verifier() -> Verifier:
    global _verifier
    if _verifier is None:
        _verifier = Verifier()
    return _verifier
