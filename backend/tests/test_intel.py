"""Engines, false-alarm filter, severity and cross-camera merge. No model weights needed:
frames are built by hand from tracks."""
from __future__ import annotations

import numpy as np

from app import config
from app.db import Store
from app.engines.accident import AccidentEngine, is_accident_class
from app.engines.baggage import BaggageEngine
from app.intel.filter import FalseAlarmFilter
from app.intel.incidents import IncidentManager
from app.intel.severity import level, score_incident
from app.schema import Candidate, Frame, Track

IMG = np.zeros((480, 640, 3), dtype=np.uint8)


def frame(ts, tracks, cam="c1", acc=None, zones=None):
    return Frame(cam, ts, IMG, tracks, True, acc, zones or [])


def person(tid, x, y=200):
    return Track(tid, "person", (x, y, x + 40, y + 120), 0.8)


def bag(x=300, y=300, conf=0.5):
    return Track(0, "suitcase", (x, y, x + 30, y + 30), conf)


# ---------------------------------------------------------------- baggage
def run_bag(scene, seconds, step=0.2):
    eng, out, t = BaggageEngine("c1"), [], 0.0
    while t <= seconds:
        out += eng.process(frame(t, scene(t)))
        t += step
    return out


def test_bag_with_owner_beside_it_is_never_flagged():
    out = run_bag(lambda t: [bag(), person(1, 290)], 60)
    assert out == []


def test_bag_flagged_after_owner_walks_away():
    # owner stands by the bag for 5 s, then walks off to the right and leaves the frame
    def scene(t):
        tr = [bag()]
        if t < 5:
            tr.append(person(1, 290))
        elif t < 9:
            tr.append(person(1, 290 + (t - 5) * 90))
        return tr

    out = run_bag(scene, 50)
    assert out, "bag should be flagged"
    first = out[0]
    assert first.subtype == "unattended"
    assert 5 + config.BAG_UNATTENDED_S <= first.ts <= 5 + config.BAG_UNATTENDED_S + 3
    assert first.details["owner_track"] == 1
    assert out[-1].subtype == "abandoned"
    assert out[-1].details["owner_away_s"] >= config.BAG_ABANDONED_S


def test_passer_by_does_not_reset_the_owner_away_clock():
    def scene(t):
        tr = [bag()]
        if t < 5:
            tr.append(person(1, 290))
        if 12 <= t < 14:
            tr.append(person(7, 280))  # a stranger walks past the bag
        return tr

    out = run_bag(scene, 25)
    assert out and out[0].ts < 5 + config.BAG_UNATTENDED_S + 3
    assert any(c.details["people_nearby"] == 1 for c in out if 12 <= c.ts < 14) or out[0].ts > 14


def test_owner_tracker_id_switch_is_not_an_abandonment():
    # the owner never moves, but the tracker gives them a new ID at t=10
    out = run_bag(lambda t: [bag(), person(1 if t < 10 else 2, 290)], 40)
    assert out == []


def test_carried_bag_is_not_flagged():
    out = run_bag(lambda t: [bag(x=100 + t * 20)], 25)
    assert out == []


# ---------------------------------------------------------------- accident
def test_accident_class_names():
    assert is_accident_class("accident") and is_accident_class("severe") and is_accident_class("Moderate")
    assert not is_accident_class("vehicle") and not is_accident_class("non-accident")
    assert not is_accident_class("Non Accident") and not is_accident_class("car")


def test_model_hit_without_a_vehicle_is_halved():
    eng = AccidentEngine("c1")
    det = [{"cls": "accident", "conf": 0.8, "box": (100, 100, 200, 200)}]
    alone = eng.process(frame(1.0, [], acc=det))[0]
    assert abs(alone.conf - 0.4) < 1e-6
    assert alone.details["vehicle_check"] != "passed"
    eng2 = AccidentEngine("c1")
    car = Track(5, "car", (110, 110, 210, 190), 0.9)
    with_car = eng2.process(frame(1.0, [car], acc=det))[0]
    assert abs(with_car.conf - 0.8) < 1e-6 and with_car.details["vehicles"] == 1


def test_vehicle_class_from_the_model_is_not_an_accident():
    eng = AccidentEngine("c1")
    assert eng.process(frame(1.0, [], acc=[{"cls": "vehicle", "conf": 0.9, "box": (0, 0, 50, 50)}])) == []


def test_trajectory_rule_fires_on_abrupt_stop_with_overlap():
    eng = AccidentEngine("c1", model_available=False)
    out, t = [], 0.0
    while t < 6:
        ax = 100 + min(t, 3.0) * 60  # car A drives right, stops dead at t=3
        a = Track(1, "car", (ax, 200, ax + 80, 250), 0.9)
        b = Track(2, "car", (330, 190, 410, 250), 0.9)  # car B parked in its path
        out += eng.process(frame(t, [a, b]))
        t += 0.2
    assert out and out[0].ts >= 3.0
    assert "trajectory rule" in out[0].details["sources"]


def test_two_parked_overlapping_cars_are_not_an_accident():
    eng = AccidentEngine("c1", model_available=False)
    out = []
    for i in range(40):
        a = Track(1, "car", (100, 200, 180, 250), 0.9)
        b = Track(2, "car", (150, 195, 230, 250), 0.9)
        out += eng.process(frame(i * 0.2, [a, b]))
    assert out == []


# ---------------------------------------------------------------- filter
def make_filter(adj=0.0, area_active=None):
    dropped = []
    return FalseAlarmFilter(lambda cam, typ: adj, dropped.append, area_active), dropped


def cand(ts, conf=0.8, typ="accident", cam="c1", box=(100, 100, 200, 200), key="accident"):
    return Candidate(typ, cam, key, conf, ts, box)


def test_single_spike_is_suppressed_as_not_persistent():
    f, dropped = make_filter()
    assert f.process(frame(0.0, []), [cand(0.0)]) == []
    f.process(frame(20.0, []), [])
    assert len(dropped) == 1 and "not persistent" in dropped[0]["reason"]
    assert f.raw_alarms == 1


def test_persistent_detection_is_confirmed():
    f, dropped = make_filter()
    got = []
    for i in range(4):
        got += f.process(frame(i * 0.6, []), [cand(i * 0.6)])
    assert got and not dropped


def test_low_confidence_is_suppressed_by_the_gate():
    f, dropped = make_filter()
    for i in range(6):
        assert f.process(frame(i * 0.6, []), [cand(i * 0.6, conf=0.3)]) == []
    f.process(frame(30.0, []), [])
    assert "below gate" in dropped[0]["reason"]


def test_dismissals_raise_the_gate():
    f, dropped = make_filter(adj=0.2)  # gate 0.45 + 0.20
    for i in range(6):
        assert f.process(frame(i * 0.6, []), [cand(i * 0.6, conf=0.6)]) == []


def test_ignore_zone_masks_a_detection():
    f, dropped = make_filter()
    zone = [{"name": "billboard", "kind": "ignore", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}]
    for i in range(6):
        assert f.process(frame(i * 0.6, [], zones=zone), [cand(i * 0.6)]) == []
    f.process(frame(30.0, []), [])
    assert "ignore zone" in dropped[0]["reason"]


def test_camera_agreement_relaxes_the_gate():
    f, _ = make_filter(area_active=lambda cam, typ, ts: True)
    got = []
    for i in range(3):
        got += f.process(frame(i * 0.6, []), [cand(i * 0.6, conf=0.40)])  # under 0.45, over 0.35
    assert got


# ---------------------------------------------------------------- severity
def test_severity_levels():
    assert [level(s) for s in (85, 80, 79, 60, 45, 10)] == ["Critical", "Critical", "High", "High", "Medium", "Low"]


def test_every_point_has_a_reason():
    score, lvl, reasons = score_incident("accident", "accident", 0.9, 12, 2,
                                         {"vehicles": 2, "people": 1, "sources": ["accident model", "trajectory rule"]})
    assert score == min(100, sum(r["points"] for r in reasons))
    assert lvl == "Critical"
    text = " ".join(r["text"] for r in reasons)
    assert "2 vehicles" in text and "2 cameras" in text


def test_abandoned_scores_above_unattended():
    d = {"owner_away_s": 35, "owner_text": "owner (track 1) away 35s"}
    assert score_incident("baggage", "abandoned", 0.5, 35, 1, d)[0] > score_incident("baggage", "unattended", 0.5, 35, 1, d)[0]


# ---------------------------------------------------------------- incidents / merge
def manager():
    events = []
    m = IncidentManager(Store(":memory:"), events.append)
    for cid, area in (("c1", "Junction"), ("c2", "Junction"), ("c3", "Hall")):
        m.set_camera({"id": cid, "name": cid.upper(), "area": area})
    return m, events


def test_same_area_cameras_merge_into_one_incident():
    m, events = manager()
    a = m.ingest(cand(10.0, 0.7, cam="c1"))
    b = m.ingest(cand(12.0, 0.6, cam="c2"))
    assert a["id"] == b["id"]
    inc = m.store.incident(a["id"])
    assert len(inc["cameras"]) == 2
    assert abs(inc["confidence"] - (1 - 0.3 * 0.4)) < 1e-6  # rises with the second camera
    assert any("2 cameras" in r["text"] for r in inc["reasons"])
    assert any("merged" in t["text"] for t in inc["timeline"])


def test_different_area_is_a_separate_incident():
    m, _ = manager()
    assert m.ingest(cand(10.0, cam="c1"))["id"] != m.ingest(cand(11.0, cam="c3"))["id"]


def test_outside_merge_window_is_a_new_incident():
    m, _ = manager()
    first = m.ingest(cand(10.0, cam="c1"))["id"]
    assert m.ingest(cand(10.0 + config.MERGE_WINDOW_S + 5, cam="c2"))["id"] != first


def test_dismiss_raises_gate_and_is_logged():
    m, _ = manager()
    iid = m.ingest(cand(10.0, cam="c1"))["id"]
    inc = m.feedback(iid, "dismiss")
    assert inc["status"] == "dismissed"
    assert m.store.threshold_adj("c1", "accident") == config.DISMISS_STEP
    assert m.store.q("SELECT action FROM feedback")[0]["action"] == "dismiss"
    # the same ongoing event stays dismissed instead of reopening
    again = m.ingest(cand(11.0, cam="c1"))
    assert again["id"] == iid and again["status"] == "dismissed"


def test_two_bags_on_one_camera_are_two_incidents():
    m, _ = manager()
    a = m.ingest(cand(10.0, 0.5, typ="baggage", cam="c3", key="bag1"))
    b = m.ingest(cand(11.0, 0.5, typ="baggage", cam="c3", key="bag2"))
    assert a["id"] != b["id"]
