"""New engines (fire, weapon, violence, medical, hazard, security) and the ML verifier.
Frames are built by hand; no model weights are needed."""
from __future__ import annotations

import json

import numpy as np

from app import config
from app.engines.extra import (FireEngine, HazardEngine, MedicalEngine, SecurityEngine, ViolenceEngine,
                               WeaponEngine)
from app.intel.filter import FalseAlarmFilter
from app.intel.verifier import Verifier, readable, summarise
from app.schema import Candidate, Frame, Track

IMG = np.zeros((480, 640, 3), dtype=np.uint8)


def frame(ts, tracks=(), aux=None, zones=None, fresh=True):
    return Frame("c1", ts, IMG, list(tracks), fresh, aux, zones or [])


def person(tid, x, y=200, w=40, h=120):
    return Track(tid, "person", (x, y, x + w, y + h), 0.8)


def scene(**groups):
    return {"groups": {g: groups.get(g, 0.0) for g in ("fire", "smoke", "explosion", "flood", "fight", "robbery",
                                                        "vandalism", "crash", "collapse", "stampede", "animal")},
            "normal": 0.1}


# ---------------------------------------------------------------- fire
def test_fire_candidate_from_detector_with_features():
    out = FireEngine("c1").process(frame(1.0, aux={"fire": {"dets": [
        {"cls": "fire", "conf": 0.7, "box": [100, 100, 200, 200]}]}}))
    assert len(out) == 1 and out[0].type == "fire" and out[0].subtype == "fire"
    f = out[0].details["features"]
    assert f["fire_conf"] == 0.7 and f["area"] > 0


def test_no_fire_without_detection_or_scene_evidence():
    assert FireEngine("c1").process(frame(1.0, aux={"fire": {"dets": []}})) == []


def test_explosion_subtype_from_scene_model():
    e = FireEngine("c1")
    e.process(frame(0.5, aux={"scene": scene(explosion=0.9, fire=0.3)}))
    out = e.process(frame(1.0, aux={"fire": {"dets": [{"cls": "smoke", "conf": 0.5, "box": [0, 0, 50, 50]}]}}))
    assert out[0].subtype == "explosion"


# ---------------------------------------------------------------- weapon
def test_weapon_held_by_person():
    out = WeaponEngine("c1").process(frame(1.0, [person(1, 100)], aux={"weapon": {"dets": [
        {"cls": "pistol", "conf": 0.8, "box": [110, 250, 130, 265]}]}}))
    assert out[0].details["held_by_person"] and out[0].subtype == "pistol"


def test_weapon_far_from_people_is_not_held():
    out = WeaponEngine("c1").process(frame(1.0, [person(1, 100)], aux={"weapon": {"dets": [
        {"cls": "knife", "conf": 0.6, "box": [500, 400, 520, 420]}]}}))
    assert out[0].details["held_by_person"] is False


# ---------------------------------------------------------------- violence
def test_violence_needs_two_people_unless_scene_agrees():
    e = ViolenceEngine("c1")
    assert e.process(frame(1.0, [person(1, 100)], aux={"violence": {"p": 0.95}})) == []
    out = e.process(frame(2.0, [person(1, 100), person(2, 150)], aux={"violence": {"p": 0.95}}))
    assert out and out[0].subtype == "fight"


def test_violence_with_a_weapon_is_robbery():
    e = ViolenceEngine("c1")
    e.process(frame(1.0, [person(1, 100), person(2, 150)],
                    aux={"weapon": {"dets": [{"cls": "pistol", "conf": 0.8, "box": [0, 0, 5, 5]}]}}))
    out = e.process(frame(2.0, [person(1, 100), person(2, 150)], aux={"violence": {"p": 0.9}}))
    assert out[0].subtype == "robbery" and out[0].details["weapon_seen"]


# ---------------------------------------------------------------- medical
def test_person_lying_still_becomes_collapse():
    e = MedicalEngine("c1")
    lying = Track(1, "person", (100, 300, 260, 360), 0.8)  # wider than tall
    out, t = [], 0.0
    while t <= config.COLLAPSE_S + 1:
        out += e.process(frame(t, [lying], aux={"fall": {"dets": []}}))
        t += 0.5
    assert out and out[-1].subtype == "collapse"


def test_fall_detector_hit_is_a_fall():
    out = MedicalEngine("c1").process(frame(1.0, [person(1, 100)], aux={"fall": {"dets": [
        {"cls": "fallen", "conf": 0.8, "box": [100, 300, 260, 360]}]}}))
    assert out[0].subtype == "fall"


# ---------------------------------------------------------------- hazard
def test_hazard_needs_margin_over_normal_scene():
    e = HazardEngine("c1")
    assert e.process(frame(1.0, aux={"scene": scene(flood=0.2)})) == []  # margin 0.1, below 0.3
    out = e.process(frame(2.0, aux={"scene": scene(flood=0.9)}))
    assert out and out[0].subtype == "flood"


# ---------------------------------------------------------------- security
RESTRICTED = [{"name": "Server room", "kind": "restricted", "points": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]}]
LANE = [{"name": "Lane 1", "kind": "lane", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}]


def test_intrusion_into_restricted_zone():
    out = SecurityEngine("c1").process(frame(1.0, [person(1, 100)], zones=RESTRICTED))
    assert any(c.subtype == "intrusion" for c in out)


def test_person_outside_restricted_zone_is_fine():
    out = SecurityEngine("c1").process(frame(1.0, [person(1, 500)], zones=RESTRICTED))
    assert not any(c.subtype == "intrusion" for c in out)


def test_wrong_way_vehicle_is_flagged_after_learning_the_lane():
    e = SecurityEngine("c1")
    out, t = [], 0.0
    for car in range(25):  # 25 cars drive left to right
        for i in range(12):
            x = 50 + i * 30
            out += e.process(frame(t, [Track(100 + car, "car", (x, 200, x + 60, 240), 0.9)], zones=LANE))
            t += 0.2
        t += 3.0
    assert not any(c.subtype == "wrong-way driving" for c in out)
    for i in range(12):  # one drives right to left
        x = 500 - i * 30
        out += e.process(frame(t, [Track(999, "car", (x, 200, x + 60, 240), 0.9)], zones=LANE))
        t += 0.2
    assert any(c.subtype == "wrong-way driving" for c in out)


# ---------------------------------------------------------------- verifier
def test_summarise_gives_mean_max_hits_duration():
    s = summarise([{"a": 1.0}, {"a": 3.0}], 4.0)
    assert s == {"hits": 2.0, "duration": 4.0, "a__mean": 2.0, "a__max": 3.0}
    assert readable("violence_p__max") == "violence model score (peak)"


def _write_model(tmp_path, typ="violence", coef=2.0, threshold=0.5):
    p = tmp_path / "v.json"
    p.write_text(json.dumps({"types": {typ: {"features": ["violence_p__mean"], "mean": [0.5], "std": [0.2],
                                             "coef": [coef], "intercept": 0.0, "threshold": threshold}}}))
    return Verifier(p)


def test_verifier_probability_and_contributions(tmp_path):
    v = _write_model(tmp_path)
    p_hi, c = v.score("violence", {"violence_p__mean": 0.9})
    p_lo, _ = v.score("violence", {"violence_p__mean": 0.2})
    assert p_hi > 0.95 > 0.5 > p_lo
    assert c[0][0] == "violence_p__mean" and c[0][1] > 0


def test_verifier_decides_instead_of_the_rule_gate(tmp_path):
    dropped = []
    f = FalseAlarmFilter(lambda cam, typ: 0.0, dropped.append)
    f.verifier = _write_model(tmp_path)
    got = []
    for i in range(8):  # rule gate for violence is 0.75; confidence 0.6 would fail it
        c = Candidate("violence", "c1", "violence", 0.6, i * 0.5, None, "fight",
                      {"features": {"violence_p": 0.9}})
        got += f.process(frame(i * 0.5), [c])
    assert got and got[0].details["verifier"]["p"] > 0.9


def test_verifier_rejects_what_the_rule_gate_would_pass(tmp_path):
    dropped = []
    f = FalseAlarmFilter(lambda cam, typ: 0.0, dropped.append)
    f.verifier = _write_model(tmp_path)
    for i in range(8):  # confidence 0.95 passes the rule gate, but the verifier sees a weak score
        c = Candidate("violence", "c1", "violence", 0.95, i * 0.5, None, "fight",
                      {"features": {"violence_p": 0.2}})
        assert f.process(frame(i * 0.5), [c]) == []
    f.flush("c1", 10.0)
    assert dropped and "ML verifier" in dropped[0]["reason"]
