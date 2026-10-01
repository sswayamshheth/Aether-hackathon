"""Scenario generators for method A. Each takes (params, cond, rng) and returns
{"cams": {cam_id: {"world": World, "area": str}}, "duration": s, "t_event": s or None, "notes": str}.

Coordinates are an unrotated 640x360 layout: traffic runs along +x, the World rotates the
whole layout by the condition's camera angle. Speeds are in pixels per second.
"""
from __future__ import annotations

import math
import random

from sim import W, World

DENSITY = {"low": 0, "med": 2, "high": 5}
CROWD_N = {"low": 10, "med": 18, "high": 28}


def _world(cond: dict, rng: random.Random) -> World:
    return World(rng, cond.get("distance", "mid"), float(cond.get("angle", 0)))


def _bg_traffic(w: World, cond: dict, rng: random.Random, dur: float, lanes=(70.0, 300.0)) -> None:
    """Steady traffic in other lanes, never touching the scripted vehicles."""
    for k in range(DENSITY.get(cond.get("density", "low"), 0)):
        y = lanes[k % len(lanes)]
        v = rng.uniform(90, 160) * (1 if k % 2 == 0 else -1)
        t0 = rng.uniform(0, dur * 0.6)
        x0 = -40 if v > 0 else W + 40
        t1 = t0 + (W + 80) / abs(v)
        w.add(rng.choice(["car", "car", "truck"]), [(t0, x0, y), (t1, x0 + v * (t1 - t0), y)], t_on=t0, t_off=t1)


def _occlude(o, cond: dict, rng: random.Random, around: float) -> None:
    if cond.get("occlusion") == "partial":
        a = around + rng.uniform(-2, 1)
        o.gaps.append((a, a + rng.uniform(0.6, 1.5)))


def _brake(t0, x0, y, v0, dur, n=8):
    """Constant deceleration from v0 to 0 over dur seconds, as keyframes (t, x, y)."""
    return [(t0 + dur * k / n, x0 + v0 * (dur * k / n) - v0 * (dur * k / n) ** 2 / (2 * dur), y) for k in range(n + 1)]


def _accel(t0, x0, y, v1, dur, n=8):
    """Constant acceleration from 0 to v1 over dur seconds."""
    return [(t0 + dur * k / n, x0 + v1 * (dur * k / n) ** 2 / (2 * dur), y) for k in range(n + 1)]


def _drive(t0, x0, y, v, t1):
    return [(t0, x0, y), (t1, x0 + v * (t1 - t0), y)]


# ---------------------------------------------------------------- accident positives
def rear_end(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    vA, vB = rng.uniform(140, 220), rng.uniform(20, 70)
    cw = w.size("car")[0]
    xa0 = 30
    xb0 = xa0 + (vA - vB) * tc + 0.8 * cw
    xa_c, xb_c = xa0 + vA * tc, xb0 + vB * tc
    y = 190
    a = w.add("car", [(0, xa0, y), (tc, xa_c, y), (tc + 0.4, xa_c + 8, y), (60, xa_c + 8, y)])
    b = w.add("car", [(0, xb0, y), (tc, xb_c, y), (tc + 0.4, xb_c + 18, y), (60, xb_c + 18, y)])
    _occlude(a, cond, rng, tc)
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


def side_impact(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    xc, yc = 330, 200
    vA, vB = rng.uniform(130, 200), rng.uniform(60, 110)
    a = w.add("car", [(0, xc - vA * tc, yc), (tc, xc - 20, yc), (tc + 0.5, xc - 10, yc + 6), (60, xc - 10, yc + 6)])
    b = w.add("car", [(0, xc + 5, yc - vB * tc), (tc, xc + 5, yc - 12), (tc + 0.5, xc + 18, yc - 8),
                      (60, xc + 18, yc - 8)])
    _occlude(b, cond, rng, tc)
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "junction"}}, "duration": tc + 20, "t_event": tc}


def head_on(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    xc, y = 320, 190
    vA, vB = rng.uniform(80, 150), rng.uniform(80, 150)
    cw = w.size("car")[0]
    w.add("car", [(0, xc - vA * tc - 0.4 * cw, y), (tc, xc - 0.4 * cw, y), (tc + 0.3, xc - 0.45 * cw, y),
                  (60, xc - 0.45 * cw, y)])
    w.add("car", [(0, xc + vB * tc + 0.4 * cw, y + 4), (tc, xc + 0.4 * cw, y + 4), (tc + 0.3, xc + 0.45 * cw, y + 4),
                  (60, xc + 0.45 * cw, y + 4)])
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


def sideswipe(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    v = rng.uniform(120, 190)
    ch = w.size("car")[1]
    y1, y2 = 180, 180 + 1.3 * ch
    x0 = 40
    xc = x0 + v * tc
    w.add("car", [(0, x0, y1), (tc - 1.0, xc - v, y1), (tc, xc, y1 + 0.45 * ch), (tc + 0.6, xc + 25, y1 + 0.5 * ch),
                  (60, xc + 25, y1 + 0.5 * ch)])
    w.add("car", [(0, x0 + 15, y2), (tc, xc + 15, y2), (tc + 0.6, xc + 35, y2 + 5), (60, xc + 35, y2 + 5)])
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


def hits_pedestrian(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    v = rng.uniform(110, 180)
    xc, y = 330, 200
    w.add("car", [(0, xc - v * tc - 30, y), (tc, xc - 30, y), (tc + 0.6, xc - 10, y), (60, xc - 10, y)])
    pw, ph = w.size("person")
    w.add("person", [(0, xc + 5, y - 90), (tc, xc + 5, y - 10), (tc + 0.4, xc + 30, y + 5), (60, xc + 30, y + 5)],
          sizes=[(pw, ph), (pw, ph), (ph, pw), (ph, pw)])
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


def two_wheeler_skid(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    v = rng.uniform(120, 200)
    y = 200
    x0 = 30
    xc = x0 + v * tc
    mw, mh = w.size("motorcycle")
    w.add("motorcycle", [(0, x0, y), (tc, xc, y), (tc + 0.8, xc + 30, y + 6), (60, xc + 30, y + 6)],
          sizes=[(mw, mh), (mw, mh), (mw * 1.6, mh * 0.6), (mw * 1.6, mh * 0.6)])
    pw, ph = w.size("person")
    w.add("person", [(0, x0, y - 12), (tc, xc, y - 12), (tc + 0.8, xc + 50, y + 4), (60, xc + 50, y + 4)],
          sizes=[(pw, ph * 0.8), (pw, ph * 0.8), (ph, pw), (ph, pw)])
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


def single_vehicle_divider(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    v = rng.uniform(150, 230)
    x0, y = 30, 200
    xc = x0 + v * tc
    w.add("car", [(0, x0, y), (tc, xc, y), (tc + 0.3, xc + 6, y + 4), (60, xc + 6, y + 4)])
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


def rollover(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    v = rng.uniform(150, 230)
    x0, y = 30, 200
    xc = x0 + v * tc
    cw, ch = w.size("car")
    w.add("car", [(0, x0, y), (tc, xc, y), (tc + 1.0, xc + 40, y + 10), (60, xc + 40, y + 10)],
          sizes=[(cw, ch), (cw, ch), (ch * 1.3, cw * 0.8), (ch * 1.3, cw * 0.8)])
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


def pileup(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    cw = w.size("car")[0]
    y = 190
    lead_x = 420
    w.add("car", [(0, lead_x - 30 * tc, y), (tc, lead_x, y), (60, lead_x, y)])  # slow lead car stops
    n = rng.choice([3, 4])
    for k in range(1, n):
        v = rng.uniform(150, 210)
        t_hit = tc + 0.5 * (k - 1)
        xh = lead_x - 0.8 * cw * k
        w.add("car", [(0, xh - v * t_hit, y), (t_hit, xh, y), (t_hit + 0.3, xh + 5, y), (60, xh + 5, y)])
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


def hit_and_run(p, cond, rng):
    w = _world(cond, rng)
    tc = rng.uniform(7, 10)
    vA, vB = rng.uniform(150, 210), rng.uniform(30, 60)
    cw = w.size("car")[0]
    y = 190
    xa0 = 30
    xb0 = xa0 + (vA - vB) * tc + 0.8 * cw
    xa_c, xb_c = xa0 + vA * tc, xb0 + vB * tc
    w.add("car", [(0, xa0, y), (tc, xa_c, y), (tc + 1.2, xa_c + 4, y), (tc + 1.8, xa_c + 4, y - 45),
                  (tc + 6, xa_c + 700, y - 45)])  # stops briefly, swerves out and flees
    w.add("car", [(0, xb0, y), (tc, xb_c, y), (tc + 0.4, xb_c + 15, y), (60, xb_c + 15, y)])
    _bg_traffic(w, cond, rng, tc + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": tc + 20, "t_event": tc}


# ---------------------------------------------------------------- traffic anomalies (zones)
def _lane_flow(w: World, rng, until: float, y: float, v: float, every: float = 1.4, start: float = 0.0):
    t = start
    while t < until:
        x0 = -40 if v > 0 else W + 40
        t1 = t + (W + 80) / abs(v)
        w.add("car", [(t, x0, y + rng.uniform(-6, 6)), (t1, x0 + v * (t1 - t), y)], t_on=t, t_off=t1)
        t += every * rng.uniform(0.8, 1.2)


def wrong_way(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(22, 28)
    w.lane("northbound", 190, "lane", 40)
    _lane_flow(w, rng, te + 15, 190, rng.uniform(110, 160))
    v = -rng.uniform(110, 170)
    w.add("car", [(te, W + 40, 172), (te + (W + 80) / abs(v), -40, 172)], t_on=te, t_off=te + (W + 80) / abs(v))
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": te + 15, "t_event": te}


def stalled(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(5, 8)
    w.lane("carriageway", 190, "lane", 40)
    xs = rng.uniform(250, 420)
    w.add("car", [(0, xs - 150 * te, 190), (te - 1, xs - 30, 190), (te, xs, 190), (80, xs, 190)])
    _lane_flow(w, rng, te + 45, 300, rng.uniform(110, 160), every=3.0)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": te + 45, "t_event": te}


def pedestrian_highway(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(5, 8)
    w.lane("carriageway", 190, "lane", 45)
    w.add("person", [(0, 100, 110), (te, 150, 185), (te + 25, 150 + rng.uniform(40, 140), 195)])
    _lane_flow(w, rng, te + 25, 300, 140, every=3.0)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": te + 25, "t_event": te}


# ---------------------------------------------------------------- accident false-alarm traps
def _queue(w, rng, n, y, x_front, gap_k, t_stop, v0, decel_s, go_again=None, cls="car"):
    """n cars approaching a stop line and queueing with centre spacing gap_k * car width,
    braking at constant deceleration over decel_s seconds (and pulling away again)."""
    cw = w.size("car")[0]
    for k in range(n):
        xs = x_front - gap_k * cw * k
        xb = xs - v0 * decel_s / 2  # where braking starts
        tb = t_stop - decel_s
        path = [(0, xb - v0 * tb, y)] + _brake(tb, xb, y, v0, decel_s)
        if go_again:
            path += _accel(go_again, xs, y, v0, decel_s)[1:]
            path += [(go_again + decel_s + 6, xs + v0 * decel_s / 2 + 6 * v0, y)]
        else:
            path += [(90, xs, y)]
        w.add(cls, path)


def stop_and_go(p, cond, rng):
    w = _world(cond, rng)
    dur = 45.0
    cw = w.size("car")[0]
    y = 190
    n = 5
    gap_k = rng.uniform(0.85, 1.05)  # perspective makes queued cars overlap in the image
    cycle = rng.uniform(6, 9)
    v = rng.uniform(50, 80)
    for k in range(n):
        path = []
        x = 480 - gap_k * cw * k
        t = 0.0
        while t < dur:
            acc = _accel(t, x, y, v, cycle / 4)
            x, t = acc[-1][1], acc[-1][0]
            br = _brake(t, x, y, v, cycle / 4)
            path += acc + br[1:]
            x, t = br[-1][1], br[-1][0]
            t += cycle / 2
            path.append((t, x, y))
        w.add("car", path)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": dur, "t_event": None}


def red_light_queue(p, cond, rng):
    w = _world(cond, rng)
    _queue(w, rng, rng.choice([3, 4, 5]), 190, 470, rng.uniform(0.8, 1.0), rng.uniform(8, 11),
           rng.uniform(90, 140), rng.uniform(1.2, 2.5), go_again=rng.uniform(25, 30))
    _bg_traffic(w, cond, rng, 40)
    return {"cams": {"cam1": {"world": w, "area": "junction"}}, "duration": 40, "t_event": None}


def parking(p, cond, rng):
    w = _world(cond, rng)
    cw = w.size("car")[0]
    w.add("car", [(0, 300, 200), (60, 300, 200)])  # parked
    x = 300 + 0.85 * cw
    w.add("car", [(0, x + 60, 190), (6, x + 10, 196), (10, x + 25, 200), (14, x + 5, 202), (18, x, 202),
                  (40, x, 202)])
    return {"cams": {"cam1": {"world": w, "area": "parking"}}, "duration": 40, "t_event": None}


def perspective_overlap(p, cond, rng):
    w = _world(cond, rng)
    ch = w.size("car")[1]
    y1, y2 = 180, 180 + 0.6 * ch
    ts = rng.uniform(8, 12)
    v = rng.uniform(100, 160)
    dec = rng.uniform(1.5, 3.0)
    for y, x0 in ((y1, 60), (y2, 90)):
        xb = x0 + v * (ts - dec)
        w.add("car", [(0, x0, y)] + _brake(ts - dec, xb, y, v, dec) + [(ts + 12, xb + v * dec / 2, y)])
    _bg_traffic(w, cond, rng, ts + 20)
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": ts + 20, "t_event": None}


def bus_occlusion(p, cond, rng):
    w = _world(cond, rng)
    ts = rng.uniform(8, 12)
    vb = rng.uniform(60, 100)
    xb = 40 + vb * (ts - 2)
    bus = w.add("bus", [(0, 40, 220)] + _brake(ts - 2, xb, 220, vb, 2.0) + [(ts + 10, xb + vb, 220)]
                + _accel(ts + 10, xb + vb, 220, vb, 3.0)[1:])
    for k in range(3):
        v = rng.uniform(110, 160)
        t0 = rng.uniform(0, 10)
        c = w.add("car", _drive(t0, -40, 190, v, t0 + 6), t_on=t0, t_off=t0 + 6)
        c.gaps.append((t0 + 2, t0 + 3.5))
    _ = bus
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": ts + 18, "t_event": None}


def u_turn(p, cond, rng):
    w = _world(cond, rng)
    cw = w.size("car")[0]
    w.add("car", [(0, 380, 170), (40, 380, 170)])  # waiting car
    x = 380 - 0.9 * cw
    w.add("car", [(0, x - 250, 190), (5, x - 20, 190), (7, x, 185), (9, x - 10, 160), (11, x - 60, 150),
                  (16, x - 400, 150)])
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": 25, "t_event": None}


def lane_merge(p, cond, rng):
    w = _world(cond, rng)
    ch = w.size("car")[1]
    v = rng.uniform(110, 160)
    tm = rng.uniform(6, 9)
    w.add("car", _drive(0, 40, 190, v, 25))
    w.add("car", [(0, 20, 190 + 1.2 * ch), (tm, 20 + v * tm, 190 + 0.6 * ch), (tm + 1.5, 20 + v * tm + 0.5 * v * 1.5, 190 + 0.3 * ch),
                  (tm + 3, 20 + v * tm + 0.5 * v * 1.5 - 20, 190), (25, 20 + v * tm + 0.5 * v * 1.5 - 20 + v * (22 - tm), 190)])
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": 25, "t_event": None}


def ambulance_stop(p, cond, rng):
    w = _world(cond, rng)
    cw = w.size("car")[0]
    xs = 330
    w.add("car", [(0, xs, 190), (60, xs, 190)])  # already stopped (breakdown)
    v = rng.uniform(100, 150)
    ts = rng.uniform(8, 11)
    xe = xs - 0.9 * cw
    dec = rng.uniform(1.2, 2.0)
    xb = xe - v * dec / 2
    w.add("truck", [(0, xb - v * (ts - dec), 188)] + _brake(ts - dec, xb, 188, v, dec) + [(40, xe, 188)])
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": ts + 20, "t_event": None}


def crowd_crossing(p, cond, rng):
    w = _world(cond, rng)
    _queue(w, rng, 3, 200, 250, rng.uniform(0.85, 1.0), 6, rng.uniform(80, 120), 2.0, go_again=30)
    n = CROWD_N.get(cond.get("density", "med"), 18)
    for k in range(n):
        t0 = rng.uniform(8, 20)
        x = rng.uniform(290, 380)
        w.add("person", [(t0, x, 100), (t0 + 6, x + rng.uniform(-20, 20), 320)], t_on=t0, t_off=t0 + 6)
    return {"cams": {"cam1": {"world": w, "area": "junction"}}, "duration": 38, "t_event": None}


def camera_shake(p, cond, rng):
    w = _world(cond, rng)
    cw = w.size("car")[0]
    for k in range(4):
        w.add("car", [(0, 470 - 0.9 * cw * k, 190), (40, 470 - 0.9 * cw * k, 190)])
    return {"cams": {"cam1": {"world": w, "area": "road"}}, "duration": 35, "t_event": None}


# ---------------------------------------------------------------- crowd
def _people(w, rng, n, x1=120, x2=520, y1=110, y2=320):
    return [(rng.uniform(x1, x2), rng.uniform(y1, y2)) for _ in range(n)]


def _mill(t0, t1, x, y, rng, step=2.0, amp=12):
    path, t = [], t0
    while t <= t1:
        path.append((t, x + rng.uniform(-amp, amp), y + rng.uniform(-amp * 0.6, amp * 0.6)))
        t += step
    return path


def panic_dispersal(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(15, 20)
    n = CROWD_N.get(cond.get("density", "med"), 18)
    cx, cy = 320, 210
    for x, y in _people(w, rng, n, 200, 440, 150, 280):
        ang = math.atan2(y - cy, x - cx) + rng.uniform(-0.3, 0.3)
        v = rng.uniform(150, 260)
        path = _mill(0, te, x, y, rng) + [(te + 0.3, x, y), (te + 4, x + v * 3.7 * math.cos(ang), y + v * 3.7 * math.sin(ang))]
        w.add("person", path)
    return {"cams": {"cam1": {"world": w, "area": "plaza"}}, "duration": te + 10, "t_event": te}


def crush_buildup(p, cond, rng):
    w = _world(cond, rng)
    n = rng.randint(34, 42)
    arrive = sorted(rng.uniform(0, 40) for _ in range(n))
    for t0 in arrive:
        x, y = rng.uniform(200, 440), rng.uniform(150, 290)
        w.add("person", [(t0, -20, y), (t0 + 4, x, y)] + _mill(t0 + 5, 70, x, y, rng, amp=4), t_on=t0)
    te = arrive[24] + 4  # the 25th person arrives
    return {"cams": {"cam1": {"world": w, "area": "concourse"}}, "duration": 55, "t_event": te}


def sudden_running(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(15, 20)
    n = max(8, CROWD_N.get(cond.get("density", "med"), 18))
    for x, y in _people(w, rng, n, 80, 300, 140, 300):
        v1, v2 = rng.uniform(20, 40), rng.uniform(180, 260)
        w.add("person", [(0, x, y), (te, x + v1 * te, y), (te + 3, x + v1 * te + v2 * 3, y + rng.uniform(-20, 20))])
    return {"cams": {"cam1": {"world": w, "area": "plaza"}}, "duration": te + 8, "t_event": te}


def fight(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(15, 20)
    for x, y in _people(w, rng, max(6, CROWD_N.get(cond.get("density", "low"), 10) // 2), 100, 540, 120, 320):
        w.add("person", _mill(0, te + 20, x, y, rng, amp=6))
    cx, cy = 320, 220
    for k in range(rng.choice([4, 5, 6])):
        path = _mill(0, te, cx + 25 * k - 50, cy, rng, amp=5)
        t = te
        while t < te + 20:
            path.append((t, cx + rng.uniform(-60, 60), cy + rng.uniform(-35, 35)))
            t += 0.3
        w.add("person", path)
    return {"cams": {"cam1": {"world": w, "area": "plaza"}}, "duration": te + 20, "t_event": te}


def surge(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(15, 20)
    n = CROWD_N.get(cond.get("density", "med"), 18)
    tx, ty = rng.uniform(250, 400), rng.uniform(160, 260)
    for x, y in _people(w, rng, n):
        d = math.hypot(tx - x, ty - y)
        v = rng.uniform(150, 220)
        w.add("person", _mill(0, te, x, y, rng) + [(te + 0.2, x, y), (te + 0.2 + d / v, tx + rng.uniform(-25, 25), ty + rng.uniform(-15, 15)),
                                                   (te + 12, tx, ty)])
    _ = n
    return {"cams": {"cam1": {"world": w, "area": "plaza"}}, "duration": te + 10, "t_event": te}


def counter_flow(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(15, 20)
    n = CROWD_N.get(cond.get("density", "med"), 18)
    for k in range(n):
        y, t0 = rng.uniform(130, 300), rng.uniform(-10, te)
        w.add("person", _drive(t0, -20, y, rng.uniform(35, 55), t0 + 30), t_on=max(0, t0))
    for k in range(6):
        y = rng.uniform(150, 280)
        w.add("person", [(te, W + 20, y), (te + 5, W + 20 - rng.uniform(160, 220) * 5, y)], t_on=te, t_off=te + 5)
    return {"cams": {"cam1": {"world": w, "area": "corridor"}}, "duration": te + 8, "t_event": te}


def overcrowding(p, cond, rng):
    w = _world(cond, rng)
    n = rng.randint(28, 36)
    for x, y in _people(w, rng, n, 60, 580, 90, 330):
        w.add("person", _mill(0, 40, x, y, rng, amp=5))
    return {"cams": {"cam1": {"world": w, "area": "platform"}}, "duration": 30, "t_event": 0.5}


def collapsed_in_crowd(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(10, 14)
    n = CROWD_N.get(cond.get("density", "med"), 18)
    for x, y in _people(w, rng, n):
        w.add("person", _drive(0, x, y, rng.uniform(-30, 30), 40))
    pw, ph = w.size("person")
    x, y = 320, 230
    w.add("person", [(0, x - 100, y), (te, x, y), (te + 0.6, x + 10, y + 12), (60, x + 10, y + 12)],
          sizes=[(pw, ph), (pw, ph), (ph * 1.1, pw), (ph * 1.1, pw)])
    return {"cams": {"cam1": {"world": w, "area": "concourse"}}, "duration": te + 25, "t_event": te}


def mob_gathering(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(8, 12)
    n = rng.randint(28, 36)
    for k in range(n):
        side = rng.choice([(-20, rng.uniform(80, 340)), (W + 20, rng.uniform(80, 340)), (rng.uniform(40, 600), -20)])
        x, y = rng.uniform(220, 420), rng.uniform(160, 280)
        t0 = rng.uniform(te - 3, te + 6)
        w.add("person", [(t0, *side), (t0 + rng.uniform(3, 6), x, y)] + _mill(t0 + 7, 60, x, y, rng, amp=8), t_on=t0)
    return {"cams": {"cam1": {"world": w, "area": "plaza"}}, "duration": te + 30, "t_event": te}


def exit_blocked(p, cond, rng):
    w = _world(cond, rng)
    w.rect_zone("exit gate", "crowd", 440, 60, 640, 360)
    n = rng.randint(26, 34)
    for x, y in _people(w, rng, n, 460, 620, 90, 330):
        w.add("person", _mill(0, 40, x, y, rng, amp=3))
    return {"cams": {"cam1": {"world": w, "area": "exit"}}, "duration": 30, "t_event": 0.5}


# crowd traps
def festival_procession(p, cond, rng):
    w = _world(cond, rng)
    n = rng.randint(26, 34)
    for k in range(n):
        y = rng.uniform(150, 280)
        x0 = rng.uniform(-300, 200)
        path = []
        for i in range(0, 41, 1):
            t = float(i)
            path.append((t, x0 + 15 * t + 10 * math.sin(t * 2.1 + k), y + 8 * math.cos(t * 1.7 + k)))
        w.add("person", path)
    return {"cams": {"cam1": {"world": w, "area": "street"}}, "duration": 40, "t_event": None}


def train_rush(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(8, 12)
    n = rng.randint(25, 35)
    for k in range(n):
        t0 = te + rng.uniform(0, 5)
        y = rng.uniform(120, 320)
        v = rng.uniform(70, 110)
        w.add("person", [(t0, 20, y), (t0 + 8, 20 + v * 8, y + rng.uniform(-15, 15))], t_on=t0, t_off=t0 + 8)
    return {"cams": {"cam1": {"world": w, "area": "platform"}}, "duration": te + 20, "t_event": None}


def bus_run(p, cond, rng):
    w = _world(cond, rng)
    for x, y in _people(w, rng, rng.randint(3, 5), 100, 300):
        w.add("person", [(0, x, y), (10, x + 10, y), (13, 560, 250)])
    for x, y in _people(w, rng, 6):
        w.add("person", _mill(0, 25, x, y, rng, amp=6))
    return {"cams": {"cam1": {"world": w, "area": "bus stop"}}, "duration": 25, "t_event": None}


def jogging(p, cond, rng):
    w = _world(cond, rng)
    n = rng.randint(6, 9)
    for k in range(n):
        y = 200 + rng.uniform(-25, 25)
        x0 = -30 - 25 * k
        w.add("person", _drive(2, x0, y, rng.uniform(110, 130), 12), t_on=2, t_off=12)
    for x, y in _people(w, rng, 4):
        w.add("person", _mill(0, 20, x, y, rng, amp=6))
    return {"cams": {"cam1": {"world": w, "area": "park"}}, "duration": 20, "t_event": None}


def rain_run(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(10, 14)
    tx, ty = 600, 120  # shelter
    for x, y in _people(w, rng, rng.randint(10, 16)):
        v = rng.uniform(120, 180)
        d = math.hypot(tx - x, ty - y)
        w.add("person", _mill(0, te, x, y, rng) + [(te + rng.uniform(0, 1.5), x, y), (te + 1.5 + d / v, tx + rng.uniform(-30, 20), ty + rng.uniform(-20, 20)),
                                                   (te + 30, tx, ty)])
    return {"cams": {"cam1": {"world": w, "area": "street"}}, "duration": te + 15, "t_event": None}


def orderly_queue(p, cond, rng):
    w = _world(cond, rng)
    n = rng.randint(15, 22)
    for k in range(n):
        x = 560 - 24 * k
        path = []
        for i in range(0, 50, 5):
            path += [(i, x + 2 * i, 220), (i + 1, x + 2 * i + 10, 220)]
        w.add("person", path)
    return {"cams": {"cam1": {"world": w, "area": "ticket counter"}}, "duration": 45, "t_event": None}


# ---------------------------------------------------------------- baggage
def _owner_with_bag(w, rng, x_stop, y, t_arrive, t_leave, leave_to, bag_cls="suitcase", det_rate=0.6,
                    bag_conf=0.55, sit=False, return_at=None, owner_gaps=()):
    pw, ph = w.size("person")
    bw, bh = w.size(bag_cls)
    x0 = -20
    bag_x, bag_y = x_stop + 0.6 * pw + bw / 2, y + ph / 2 - bh / 2
    size_p = (pw * 1.2, ph * 0.7) if sit else (pw, ph)
    path = [(0, x0, y), (t_arrive, x_stop, y), (t_leave, x_stop, y), (t_leave + 8, leave_to[0], leave_to[1])]
    sizes = [(pw, ph), size_p, size_p, (pw, ph)]
    if return_at:
        path += [(return_at - 3, leave_to[0], leave_to[1]), (return_at, x_stop, y), (return_at + 30, x_stop, y)]
        sizes += [(pw, ph), (pw, ph), (pw, ph)]
    owner = w.add("person", path, sizes=sizes, t_on=0)
    owner.gaps.extend(owner_gaps)
    bag = w.add(bag_cls, [(0, x0 + 12, y + 6), (t_arrive, bag_x, bag_y), (200, bag_x, bag_y)],
                det_rate=det_rate, conf=bag_conf)
    return owner, bag


def bag_dropped(p, cond, rng, **kw):
    w = _world(cond, rng)
    ta = rng.uniform(6, 9)
    tl = ta + rng.uniform(3, 6)
    y = rng.uniform(170, 260)
    _owner_with_bag(w, rng, rng.uniform(250, 400), y, ta, tl, (W + 30, y + rng.uniform(-40, 40)),
                    det_rate=float(p.get("det_rate", 0.6)), bag_conf=float(p.get("bag_conf", 0.55)), **kw)
    for x, yy in _people(w, rng, DENSITY.get(cond.get("density", "low"), 0) * 2):
        t0 = rng.uniform(0, 30)
        w.add("person", _drive(t0, -20, yy, rng.uniform(40, 70), t0 + 14), t_on=t0, t_off=t0 + 14)
    return {"cams": {"cam1": {"world": w, "area": "hall"}}, "duration": tl + 45, "t_event": tl + 1.5}


def bag_bench(p, cond, rng):
    return bag_dropped(p, cond, rng, sit=True)


def bag_under_seat(p, cond, rng):
    return bag_dropped({"det_rate": 0.3, "bag_conf": 0.45}, cond, rng, sit=True, bag_cls="backpack")


def bag_behind_pillar(p, cond, rng):
    r = bag_dropped({"det_rate": 0.4, "bag_conf": 0.5}, cond, rng)
    bag = [o for o in r["cams"]["cam1"]["world"].objs if o.cls == "suitcase"][0]
    t = r["t_event"]
    while t < r["duration"]:
        bag.gaps.append((t, t + rng.uniform(2, 5)))
        t += rng.uniform(6, 10)
    return r


def bag_dense_crowd(p, cond, rng):
    r = bag_dropped(p, cond, rng)
    w = r["cams"]["cam1"]["world"]
    bag = [o for o in w.objs if o.cls == "suitcase"][0]
    bx, by = bag.keys[-1][1], bag.keys[-1][2]
    for k in range(25):
        t0 = rng.uniform(0, r["duration"])
        yy = by + rng.uniform(-40, 40)
        w.add("person", [(t0, -20, yy), (t0 + 10, W + 20, yy + rng.uniform(-20, 20))], t_on=t0, t_off=t0 + 10)
    bag.det_rate = 0.45
    _ = bx
    return r


def bag_owner_leaves_view(p, cond, rng):
    return bag_dropped(p, cond, rng)  # leave_to is already outside the frame


def group_bags(p, cond, rng):
    w = _world(cond, rng)
    ta = rng.uniform(6, 9)
    tl = ta + rng.uniform(3, 6)
    for k in range(3):
        y = 150 + 55 * k
        _owner_with_bag(w, rng, 200 + 90 * k, y, ta + 0.5 * k, tl, (W + 30, y), det_rate=0.65)
    return {"cams": {"cam1": {"world": w, "area": "hall"}}, "duration": tl + 45, "t_event": tl + 1.5}


def bag_restricted_zone(p, cond, rng):
    r = bag_dropped(p, cond, rng)
    w = r["cams"]["cam1"]["world"]
    bag = [o for o in w.objs if o.cls == "suitcase"][0]
    bx, by = bag.keys[-1][1], bag.keys[-1][2]
    w.zones.append({"name": "platform edge", "kind": "restricted",
                    "points": [[(bx - 60) / W, (by - 50) / 360], [(bx + 60) / W, (by - 50) / 360],
                               [(bx + 60) / W, (by + 50) / 360], [(bx - 60) / W, (by + 50) / 360]]})
    return r


# baggage traps
def owner_returns(p, cond, rng):
    w = _world(cond, rng)
    ta = rng.uniform(6, 9)
    tl = ta + rng.uniform(3, 6)
    y = rng.uniform(170, 260)
    _owner_with_bag(w, rng, 330, y, ta, tl, (330 + rng.uniform(120, 200), y), return_at=tl + rng.uniform(4, 7))
    return {"cams": {"cam1": {"world": w, "area": "hall"}}, "duration": tl + 40, "t_event": None}


def owner_occluded(p, cond, rng):
    w = _world(cond, rng)
    ta = 6.0
    gaps = []
    t = 10.0
    while t < 50:
        gaps.append((t, t + rng.uniform(2, 5)))
        t += rng.uniform(7, 11)
    y = rng.uniform(170, 260)
    _owner_with_bag(w, rng, 330, y, ta, 200, (W + 30, y), owner_gaps=gaps)
    return {"cams": {"cam1": {"world": w, "area": "hall"}}, "duration": 55, "t_event": None}


def handover(p, cond, rng):
    w = _world(cond, rng)
    ta, th = 6.0, rng.uniform(10, 13)
    y = 220
    owner, bag = _owner_with_bag(w, rng, 300, y, ta, th + 2, (W + 30, y))
    bx, by = bag.keys[1][1], bag.keys[1][2]
    w.add("person", [(0, W + 20, y + 10), (th - 1, bx + 15, y + 10), (th + 1, bx + 15, y + 10), (th + 9, -30, y + 10)])
    bw_, bh_ = bag.keys[1][3], bag.keys[1][4]
    bag.keys = [bag.keys[0], bag.keys[1], (th + 1, bx, by, bw_, bh_), (th + 9, -25, by, bw_, bh_)]
    bag.t_off = th + 9
    return {"cams": {"cam1": {"world": w, "area": "hall"}}, "duration": th + 35, "t_event": None}


def sitting_with_bag(p, cond, rng):
    w = _world(cond, rng)
    y = rng.uniform(170, 260)
    _owner_with_bag(w, rng, 320, y, 6, 200, (W + 30, y), sit=True)
    for x, yy in _people(w, rng, 4):
        w.add("person", _mill(0, 70, x, yy, rng, amp=10))
    return {"cams": {"cam1": {"world": w, "area": "waiting room"}}, "duration": 70, "t_event": None}


def luggage_trolley(p, cond, rng):
    w = _world(cond, rng)
    y = 220
    ts = rng.uniform(8, 10)
    pw, ph = w.size("person")
    stop = 320
    path = [(0, -20, y), (ts, stop, y), (ts + 8, stop, y), (ts + 16, W + 30, y)]
    w.add("person", path)
    for k in range(2):
        off = pw * (0.9 + 0.5 * k)
        w.add("suitcase", [(t, x + off, yy + 8) for t, x, yy in path], det_rate=0.7, conf=0.6)
    return {"cams": {"cam1": {"world": w, "area": "station"}}, "duration": ts + 30, "t_event": None}


def bin_box_stroller(p, cond, rng):
    w = _world(cond, rng)
    conf = rng.uniform(0.2, 0.45)
    x, y = rng.uniform(200, 450), rng.uniform(180, 280)
    w.add(rng.choice(["suitcase", "backpack", "handbag"]), [(0, x, y), (80, x, y)], det_rate=0.5, conf=conf)
    for k in range(6):
        t0 = rng.uniform(0, 50)
        yy = rng.uniform(120, 320)
        w.add("person", _drive(t0, -20, yy, rng.uniform(40, 70), t0 + 14), t_on=t0, t_off=t0 + 14)
    return {"cams": {"cam1": {"world": w, "area": "hall"}}, "duration": 70, "t_event": None,
            "notes": f"a static non-bag object that the detector labels as a bag at confidence {conf:.2f}"}


def bag_taken_by_stranger(p, cond, rng):
    w = _world(cond, rng)
    ta = 6.0
    tl = ta + 4
    y = 220
    owner, bag = _owner_with_bag(w, rng, 300, y, ta, tl, (W + 30, y))
    bx, by = bag.keys[1][1], bag.keys[1][2]
    tt = tl + rng.uniform(18, 25)
    w.add("person", [(tt - 5, -20, y + 30), (tt, bx - 12, y + 10), (tt + 1, bx - 12, y + 10), (tt + 8, -30, y + 30)],
          t_on=tt - 5, t_off=tt + 8)
    bw_, bh_ = bag.keys[1][3], bag.keys[1][4]
    bag.keys = [bag.keys[0], bag.keys[1], (tt + 1, bx, by, bw_, bh_), (tt + 8, -25, by + 20, bw_, bh_)]
    bag.t_off = tt + 8
    return {"cams": {"cam1": {"world": w, "area": "hall"}}, "duration": tt + 15, "t_event": tl + 1.5}


# ---------------------------------------------------------------- other suspicious
def loitering(p, cond, rng):
    w = _world(cond, rng)
    x, y = rng.uniform(200, 440), rng.uniform(170, 260)
    w.add("person", [(0, -20, y), (4, x, y)] + _mill(5, 90, x, y, rng, step=3, amp=18))
    return {"cams": {"cam1": {"world": w, "area": "gate"}}, "duration": 80, "t_event": 64}


def intrusion(p, cond, rng):
    w = _world(cond, rng)
    w.rect_zone("railway track", "restricted", 360, 60, 520, 330)
    te = rng.uniform(8, 12)
    y = rng.uniform(150, 280)
    w.add("person", [(0, 60, y), (te, 380, y), (te + 10, 450, y + 20)])
    return {"cams": {"cam1": {"world": w, "area": "track"}}, "duration": te + 15, "t_event": te}


def fall_alone(p, cond, rng):
    w = _world(cond, rng)
    te = rng.uniform(8, 12)
    pw, ph = w.size("person")
    y = rng.uniform(170, 260)
    x = 300
    w.add("person", [(0, 60, y), (te, x, y), (te + 0.6, x + 10, y + 15), (60, x + 10, y + 15)],
          sizes=[(pw, ph), (pw, ph), (ph * 1.1, pw), (ph * 1.1, pw)])
    return {"cams": {"cam1": {"world": w, "area": "corridor"}}, "duration": te + 20, "t_event": te}


# ---------------------------------------------------------------- system
def multi_cam_same(p, cond, rng):
    ncam = int(p.get("cameras", 2))
    base_seed = rng.random()
    out = {"cams": {}, "duration": 0, "t_event": None}
    for k in range(ncam):
        r2 = random.Random(base_seed)  # same event timing on every camera
        c2 = dict(cond, angle=(float(cond.get("angle", 0)) + 35 * k) % 90,
                  distance=["near", "mid", "far"][(["near", "mid", "far"].index(cond.get("distance", "mid")) + k) % 3])
        r = rear_end(p, c2, r2)
        out["cams"][f"cam{k + 1}"] = {"world": r["cams"]["cam1"]["world"], "area": "junction-A"}
        out["duration"], out["t_event"] = r["duration"], r["t_event"]
    return out


def two_separate(p, cond, rng):
    a = rear_end(p, cond, random.Random(rng.random()))
    b = (bag_dropped if p.get("second") == "baggage" else side_impact)(p, cond, random.Random(rng.random()))
    same_area = bool(p.get("same_area"))
    return {"cams": {"cam1": {"world": a["cams"]["cam1"]["world"], "area": "area-A"},
                     "cam2": {"world": b["cams"]["cam1"]["world"], "area": "area-A" if same_area else "area-B"}},
            "duration": max(a["duration"], b["duration"]), "t_event": a["t_event"],
            "t_event2": b["t_event"]}


GENERATORS = {name: fn for name, fn in globals().items()
              if callable(fn) and not name.startswith("_") and fn.__module__ == __name__
              and name not in {"World"}}
