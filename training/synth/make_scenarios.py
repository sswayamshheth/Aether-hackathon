"""Write the scenario spec files: tests/scenarios/<category>/<id>.yaml.

    backend\\.venv\\Scripts\\python training\\synth\\make_scenarios.py

Ten condition variants per edge case (day/night, weather, density, distance, camera angle,
occlusion, detection rate, ID switches, camera shake). Expected outcomes are written into
every spec, relative to the scripted event time t_event.
"""
from __future__ import annotations

import shutil
import zlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests" / "scenarios"

VARIANTS = [
    dict(light="day", weather="clear", density="low", distance="mid", angle=0, occlusion="none", fps=5),
    dict(light="night", weather="clear", density="med", distance="mid", angle=30, occlusion="none", fps=5),
    dict(light="day", weather="rain", density="high", distance="near", angle=60, occlusion="partial", fps=5),
    dict(light="day", weather="fog", density="low", distance="far", angle=90, occlusion="none", fps=5),
    dict(light="night", weather="rain", density="med", distance="near", angle=0, occlusion="partial", fps=3),
    dict(light="day", weather="clear", density="high", distance="far", angle=30, occlusion="partial", fps=5,
         id_switch=True),
    dict(light="day", weather="clear", density="med", distance="near", angle=45, occlusion="none", fps=10,
         jitter=0.04),
    dict(light="night", weather="fog", density="low", distance="mid", angle=60, occlusion="none", fps=5, miss=0.1),
    dict(light="day", weather="rain", density="low", distance="mid", angle=15, occlusion="partial", fps=3,
         id_switch=True),
    dict(light="day", weather="clear", density="med", distance="far", angle=75, occlusion="none", fps=5, shake=3),
]

ACC = {"event": "accident", "window_s": [-1, 6]}
BAG = {"event": "baggage", "window_s": [7, 30]}
NO = lambda *t: {"forbid": list(t)}  # noqa: E731

# (category, case, generator, params, expected, description)
CASES = [
    # accident / traffic positives
    ("accident_positive", "rear_end", "rear_end", {}, ACC, "a moving car runs into the back of a slower car; both stop"),
    ("accident_positive", "side_impact", "side_impact", {}, ACC, "T-bone at a junction; both stop"),
    ("accident_positive", "head_on", "head_on", {}, ACC, "two cars meet head-on in one lane"),
    ("accident_positive", "sideswipe", "sideswipe", {}, ACC, "a car drifts into the next lane, both brake to a stop"),
    ("accident_positive", "vehicle_hits_pedestrian", "hits_pedestrian", {}, ACC,
     "a car hits a crossing pedestrian, who ends up lying on the road"),
    ("accident_positive", "two_wheeler_skid", "two_wheeler_skid", {}, ACC,
     "a motorcycle skids and falls; rider lying next to it; no second vehicle"),
    ("accident_positive", "single_vehicle_divider", "single_vehicle_divider", {}, ACC,
     "a single car stops dead against an undetected divider or pole"),
    ("accident_positive", "rollover", "rollover", {}, ACC, "a single car rolls over (box shape flips) and stops"),
    ("accident_positive", "pileup", "pileup", {}, ACC, "three or four cars chain-collide behind a stopping car"),
    ("accident_positive", "hit_and_run", "hit_and_run", {}, ACC, "a car rear-ends another, pauses, swerves out and flees"),
    ("traffic_anomaly", "wrong_way", "wrong_way", {},
     {"event": "security", "subtype": "wrong-way", "window_s": [-1, 5]}, "one car drives against the lane's flow"),
    ("traffic_anomaly", "stalled_vehicle", "stalled", {},
     {"event": "security", "subtype": "stalled", "window_s": [25, 42]}, "a car stops in a live lane for 40 s"),
    ("traffic_anomaly", "pedestrian_on_highway", "pedestrian_highway", {},
     {"event": "security", "subtype": "pedestrian", "window_s": [-1, 8]}, "a person walks onto the carriageway"),
    # accident traps
    ("accident_trap", "stop_and_go", "stop_and_go", {}, NO("accident"), "queued cars creeping in stop-and-go traffic"),
    ("accident_trap", "red_light_queue", "red_light_queue", {}, NO("accident"), "cars brake and queue at a red light"),
    ("accident_trap", "parking", "parking", {}, NO("accident"), "slow parking manoeuvre next to a parked car"),
    ("accident_trap", "perspective_overlap", "perspective_overlap", {}, NO("accident"),
     "two cars in adjacent lanes overlap in the image and brake together at a signal"),
    ("accident_trap", "bus_occlusion", "bus_occlusion", {}, NO("accident"), "a bus hides cars and stops at a bus stop"),
    ("accident_trap", "u_turn", "u_turn", {}, NO("accident"), "a car slows and U-turns beside a waiting car"),
    ("accident_trap", "lane_merge", "lane_merge", {}, NO("accident"), "a car merges and the other yields"),
    ("accident_trap", "ambulance_stop", "ambulance_stop", {}, NO("accident"),
     "an ambulance or police vehicle brakes and stops beside a stopped car on purpose"),
    ("accident_trap", "crowd_crossing", "crowd_crossing", {}, NO("accident"),
     "people cross in front of cars stopped at a signal"),
    ("accident_trap", "camera_shake", "camera_shake", {"shake": True}, NO("accident"),
     "queued cars, camera shaking in the wind"),
    # crowd positives
    ("crowd_positive", "panic_dispersal", "panic_dispersal", {}, {"event": "crowd", "window_s": [-1, 6]},
     "a milling crowd suddenly runs outward"),
    ("crowd_positive", "crush_buildup", "crush_buildup", {}, {"event": "crowd", "window_s": [-1, 12]},
     "people keep arriving until the area holds 34-42"),
    ("crowd_positive", "sudden_running", "sudden_running", {}, {"event": "crowd", "window_s": [-1, 6]},
     "a walking group all break into a run"),
    ("crowd_positive", "fight", "fight", {}, {"event": ["crowd", "violence"], "window_s": [-1, 8]},
     "four to six people brawling among bystanders"),
    ("crowd_positive", "surge", "surge", {}, {"event": "crowd", "window_s": [-1, 6]}, "everyone rushes to one point"),
    ("crowd_positive", "counter_flow", "counter_flow", {}, {"event": "crowd", "window_s": [-1, 6]},
     "a group runs against the flow of a walking stream"),
    ("crowd_positive", "overcrowding", "overcrowding", {}, {"event": "crowd", "window_s": [-1, 15]},
     "28-36 people in view, above the limit"),
    ("crowd_positive", "collapsed_in_crowd", "collapsed_in_crowd", {}, {"event": "medical", "window_s": [-1, 16]},
     "one person collapses and lies still inside a moving crowd"),
    ("crowd_positive", "mob_gathering", "mob_gathering", {}, {"event": "crowd", "window_s": [-1, 15]},
     "people converge from all sides into a mob of 28-36"),
    ("crowd_positive", "exit_blocked", "exit_blocked", {}, {"event": "crowd", "window_s": [-1, 15]},
     "a dense crowd stands in the exit zone"),
    # crowd traps
    ("crowd_trap", "festival_procession", "festival_procession", {}, {"forbid_above": {"crowd": "Low"}},
     "a slow, dancing procession"),
    ("crowd_trap", "train_arrival_rush", "train_rush", {}, {"forbid_above": {"crowd": "Low"}},
     "a Mumbai local empties onto the platform and everyone walks briskly one way"),
    ("crowd_trap", "running_for_bus", "bus_run", {}, {"forbid_above": {"crowd": "Low"}},
     "three to five people run for a bus"),
    ("crowd_trap", "jogging_group", "jogging", {}, {"forbid_above": {"crowd": "Low"}}, "a jogging group passes"),
    ("crowd_trap", "running_from_rain", "rain_run", {}, {"forbid_above": {"crowd": "Low"}},
     "people run to a shelter when it starts to rain"),
    ("crowd_trap", "orderly_queue", "orderly_queue", {}, {"forbid_above": {"crowd": "Low"}},
     "an orderly queue shuffling forward"),
    # baggage positives
    ("baggage_positive", "dropped_owner_walks_away", "bag_dropped", {}, BAG, "owner puts a suitcase down and walks off"),
    ("baggage_positive", "left_on_bench", "bag_bench", {}, BAG, "owner sits, leaves the bag on the bench"),
    ("baggage_positive", "under_seat", "bag_under_seat", {}, BAG, "a backpack under a seat, seldom detected"),
    ("baggage_positive", "behind_pillar", "bag_behind_pillar", {}, BAG, "bag partly hidden by a pillar (long gaps)"),
    ("baggage_positive", "dense_crowd", "bag_dense_crowd", {}, BAG, "bag left while a crowd keeps walking past it"),
    ("baggage_positive", "owner_leaves_view", "bag_owner_leaves_view", {}, BAG, "owner leaves the camera view"),
    ("baggage_positive", "group_bags", "group_bags", {}, dict(BAG, count=3), "three people leave three bags together"),
    ("baggage_positive", "restricted_zone", "bag_restricted_zone", {}, dict(BAG, min_severity="High"),
     "bag left inside a restricted zone"),
    # baggage traps
    ("baggage_trap", "owner_returns", "owner_returns", {}, NO("baggage"), "owner comes back within 4-7 s"),
    ("baggage_trap", "owner_briefly_occluded", "owner_occluded", {}, NO("baggage"),
     "owner stays by the bag but is repeatedly hidden for 2-5 s"),
    ("baggage_trap", "handed_to_other", "handover", {}, NO("baggage"), "bag handed to another person who carries it away"),
    ("baggage_trap", "sitting_with_bag", "sitting_with_bag", {}, NO("baggage"), "person sits beside their bag"),
    ("baggage_trap", "luggage_trolley", "luggage_trolley", {}, NO("baggage"), "trolley with suitcases stops 8 s at a kiosk"),
    ("baggage_trap", "bin_box_stroller", "bin_box_stroller", {}, NO("baggage"),
     "a bin, box or stroller detected as a bag at low confidence, no owner"),
    ("baggage_documented", "taken_by_stranger", "bag_taken_by_stranger", {},
     dict(BAG, note="no 'bag removed' event exists; expected behaviour is the unattended alarm only"),
     "bag left, a stranger takes it 18-25 s later"),
    # other suspicious
    ("other", "loitering", "loitering", {}, {"event": "security", "subtype": "loiter", "window_s": [-6, 10]},
     "one person stays near a gate for 80 s"),
    ("other", "intrusion", "intrusion", {}, {"event": "security", "subtype": "intrusion", "window_s": [-1, 5]},
     "a person walks onto a railway track zone"),
    ("other", "fall_alone", "fall_alone", {}, {"event": "medical", "window_s": [-1, 16]}, "a person falls and lies still"),
    # system
    ("system", "rtsp_reconnect_bag", "bag_dropped", {"stream_gap": True}, BAG | {"window_s": [7, 45]},
     "the stream drops for 4-8 s while a bag is being left; pipeline resets on reconnect"),
    ("system", "rtsp_reconnect_accident", "rear_end", {"stream_gap_after": True}, ACC | {"count": 1},
     "the stream drops for 4-8 s just after a crash; must not raise a duplicate"),
    ("system", "low_fps_bag", "bag_dropped", {"cam_fps": 2}, BAG, "camera delivers 2 fps"),
    ("system", "low_fps_accident", "rear_end", {"cam_fps": 3}, ACC, "camera delivers 3 fps"),
    ("system", "same_incident_2cams", "multi_cam_same", {"cameras": 2}, ACC | {"count": 1, "min_cameras": 2},
     "one crash seen by two cameras: one merged incident"),
    ("system", "same_incident_3cams", "multi_cam_same", {"cameras": 3}, ACC | {"count": 1, "min_cameras": 2},
     "one crash seen by three cameras: one merged incident"),
    ("system", "two_incidents_two_areas", "two_separate", {}, ACC | {"count": 2},
     "two crashes at the same time in different areas: two incidents"),
    ("system", "crash_and_bag_same_area", "two_separate", {"second": "baggage", "same_area": True},
     ACC | {"also": {"event": "baggage", "window_s": [7, 30], "ref": "t_event2"}},
     "a crash on cam1 and a bag on cam2 in the same area: two incidents of different types"),
]


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    n = 0
    counts: dict[str, int] = {}
    for cat, case, gen, params, expected, desc in CASES:
        for i, v in enumerate(VARIANTS):
            cond = dict(v)
            p = dict(params)
            if p.pop("shake", False):
                cond["shake"] = 6 + i
            if p.pop("stream_gap", False):
                cond["stream_gap_rel"] = [3.0, 3.0 + 4 + (i % 5)]
            if p.pop("stream_gap_after", False):
                cond["stream_gap_rel"] = [2.5, 2.5 + 4 + (i % 5)]
            if "cam_fps" in p:
                cond["cam_fps"] = p.pop("cam_fps")
                cond["fps"] = cond["cam_fps"]
            sid = f"{case}_{i + 1:02d}"
            spec = {"id": sid, "category": cat, "case": case, "method": "A (trajectory-level)",
                    "description": desc, "generator": {"kind": gen, "params": p},
                    "seed": zlib.crc32(sid.encode()) & 0xFFFFFF, "conditions": cond,
                    "models": "silent (auxiliary models answer on their live cadence with nothing detected)",
                    "expected": expected}
            d = OUT / cat
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{sid}.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
            n += 1
            counts[cat] = counts.get(cat, 0) + 1
    print(n, "scenarios", counts)


if __name__ == "__main__":
    main()
