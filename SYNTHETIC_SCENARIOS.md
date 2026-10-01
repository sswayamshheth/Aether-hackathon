# SYNTHETIC_SCENARIOS.md

Every synthetic scenario, how it is generated and what the system is expected to do. Spec files live in
`tests/scenarios/<category>/<id>.yaml`; results are in `docs/results/synthetic_suite*.json` (method A) and
`docs/results/synthetic_pixel*.json` (method B). **Synthetic results are never mixed with real results.**

Methods

- **A, trajectory-level** (`training/synth/`): scripted boxes for people, vehicles and bags, turned into
  detector-like output (misses, jitter, ID switches, occlusion gaps, detection rate, camera shake, lower
  confidence at night / in rain / fog) and replayed through the real Pipeline, filter and incident manager.
  The vision models are silent, so A tests the logic: rules, timing, thresholds, severity and cross-camera merge.
- **B, pixel-level**: real labelled clips re-run through the full detector + tracker + engines with an image
  condition on every frame (night, rain, fog, JPEG q10, low resolution, motion blur, shake, noise, infrared
  grayscale, dropped frames, an occluding mask). Ground truth carries over from the real labels.
- **C, composited baggage scenes**: not built tonight (see OVERNIGHT_REPORT.md, known gaps). Baggage timing
  cases are covered by method A instead.

Every method A case runs in ten condition variants: day/night, clear/rain/fog, low/medium/high density,
near/mid/far, camera angle 0-90 degrees, with or without occlusion gaps, 3/5/10 detections per second, ID
switches, jitter and shake.

## Counts

| Category | Scenarios |
|---|---|
| accident_positive | 100 |
| accident_trap | 100 |
| baggage_documented | 10 |
| baggage_positive | 80 |
| baggage_trap | 60 |
| crowd_positive | 100 |
| crowd_trap | 60 |
| other | 30 |
| pixel_accident | 12 |
| pixel_baggage | 12 |
| pixel_crowd | 12 |
| system | 80 |
| traffic_anomaly | 30 |
| **total** | **686** |

## Scenarios

| Category | Case | Method | Variants | Generated as | Expected outcome | Passing (latest run) |
|---|---|---|---|---|---|---|
| accident_positive | head_on | A | 10 | two cars meet head-on in one lane | accident, raised between t-1 s and t+6 s of the scripted event | 7/10 |
| accident_positive | hit_and_run | A | 10 | a car rear-ends another, pauses, swerves out and flees | accident, raised between t-1 s and t+6 s of the scripted event | 6/10 |
| accident_positive | pileup | A | 10 | three or four cars chain-collide behind a stopping car | accident, raised between t-1 s and t+6 s of the scripted event | 7/10 |
| accident_positive | rear_end | A | 10 | a moving car runs into the back of a slower car; both stop | accident, raised between t-1 s and t+6 s of the scripted event | 6/10 |
| accident_positive | rollover | A | 10 | a single car rolls over (box shape flips) and stops | accident, raised between t-1 s and t+6 s of the scripted event | 0/10 |
| accident_positive | side_impact | A | 10 | T-bone at a junction; both stop | accident, raised between t-1 s and t+6 s of the scripted event | 5/10 |
| accident_positive | sideswipe | A | 10 | a car drifts into the next lane, both brake to a stop | accident, raised between t-1 s and t+6 s of the scripted event | 10/10 |
| accident_positive | single_vehicle_divider | A | 10 | a single car stops dead against an undetected divider or pole | accident, raised between t-1 s and t+6 s of the scripted event | 0/10 |
| accident_positive | two_wheeler_skid | A | 10 | a motorcycle skids and falls; rider lying next to it; no second vehicle | accident, raised between t-1 s and t+6 s of the scripted event | 0/10 |
| accident_positive | vehicle_hits_pedestrian | A | 10 | a car hits a crossing pedestrian, who ends up lying on the road | accident, raised between t-1 s and t+6 s of the scripted event | 0/10 |
| accident_trap | ambulance_stop | A | 10 | an ambulance or police vehicle brakes and stops beside a stopped car on purpose | no accident incident | 6/10 |
| accident_trap | bus_occlusion | A | 10 | a bus hides cars and stops at a bus stop | no accident incident | 10/10 |
| accident_trap | camera_shake | A | 10 | queued cars, camera shaking in the wind | no accident incident | 4/10 |
| accident_trap | crowd_crossing | A | 10 | people cross in front of cars stopped at a signal | no accident incident | 0/10 |
| accident_trap | lane_merge | A | 10 | a car merges and the other yields | no accident incident | 8/10 |
| accident_trap | parking | A | 10 | slow parking manoeuvre next to a parked car | no accident incident | 10/10 |
| accident_trap | perspective_overlap | A | 10 | two cars in adjacent lanes overlap in the image and brake together at a signal | no accident incident | 1/10 |
| accident_trap | red_light_queue | A | 10 | cars brake and queue at a red light | no accident incident | 0/10 |
| accident_trap | stop_and_go | A | 10 | queued cars creeping in stop-and-go traffic | no accident incident | 0/10 |
| accident_trap | u_turn | A | 10 | a car slows and U-turns beside a waiting car | no accident incident | 8/10 |
| baggage_documented | taken_by_stranger | A | 10 | bag left, a stranger takes it 18-25 s later | baggage, raised between t+7 s and t+30 s of the scripted event (no 'bag removed' event exists; expected behaviour is the unattended alarm only) | 7/10 |
| baggage_positive | behind_pillar | A | 10 | bag partly hidden by a pillar (long gaps) | baggage, raised between t+7 s and t+30 s of the scripted event | 7/10 |
| baggage_positive | dense_crowd | A | 10 | bag left while a crowd keeps walking past it | baggage, raised between t+7 s and t+30 s of the scripted event | 7/10 |
| baggage_positive | dropped_owner_walks_away | A | 10 | owner puts a suitcase down and walks off | baggage, raised between t+7 s and t+30 s of the scripted event | 8/10 |
| baggage_positive | group_bags | A | 10 | three people leave three bags together | baggage, raised between t+7 s and t+30 s of the scripted event, exactly 3 incident(s) | 8/10 |
| baggage_positive | left_on_bench | A | 10 | owner sits, leaves the bag on the bench | baggage, raised between t+7 s and t+30 s of the scripted event | 7/10 |
| baggage_positive | owner_leaves_view | A | 10 | owner leaves the camera view | baggage, raised between t+7 s and t+30 s of the scripted event | 7/10 |
| baggage_positive | restricted_zone | A | 10 | bag left inside a restricted zone | baggage, raised between t+7 s and t+30 s of the scripted event, severity at least High | 8/10 |
| baggage_positive | under_seat | A | 10 | a backpack under a seat, seldom detected | baggage, raised between t+7 s and t+30 s of the scripted event | 5/10 |
| baggage_trap | bin_box_stroller | A | 10 | a bin, box or stroller detected as a bag at low confidence, no owner | no baggage incident | 8/10 |
| baggage_trap | handed_to_other | A | 10 | bag handed to another person who carries it away | no baggage incident | 10/10 |
| baggage_trap | luggage_trolley | A | 10 | trolley with suitcases stops 8 s at a kiosk | no baggage incident | 10/10 |
| baggage_trap | owner_briefly_occluded | A | 10 | owner stays by the bag but is repeatedly hidden for 2-5 s | no baggage incident | 10/10 |
| baggage_trap | owner_returns | A | 10 | owner comes back within 4-7 s | no baggage incident | 10/10 |
| baggage_trap | sitting_with_bag | A | 10 | person sits beside their bag | no baggage incident | 10/10 |
| crowd_positive | collapsed_in_crowd | A | 10 | one person collapses and lies still inside a moving crowd | medical, raised between t-1 s and t+16 s of the scripted event | 0/10 |
| crowd_positive | counter_flow | A | 10 | a group runs against the flow of a walking stream | crowd, raised between t-1 s and t+6 s of the scripted event | 2/10 |
| crowd_positive | crush_buildup | A | 10 | people keep arriving until the area holds 34-42 | crowd, raised between t-1 s and t+12 s of the scripted event | 7/10 |
| crowd_positive | exit_blocked | A | 10 | a dense crowd stands in the exit zone | crowd, raised between t-1 s and t+15 s of the scripted event | 7/10 |
| crowd_positive | fight | A | 10 | four to six people brawling among bystanders | crowd or violence, raised between t-1 s and t+8 s of the scripted event | 0/10 |
| crowd_positive | mob_gathering | A | 10 | people converge from all sides into a mob of 28-36 | crowd, raised between t-1 s and t+15 s of the scripted event | 7/10 |
| crowd_positive | overcrowding | A | 10 | 28-36 people in view, above the limit | crowd, raised between t-1 s and t+15 s of the scripted event | 7/10 |
| crowd_positive | panic_dispersal | A | 10 | a milling crowd suddenly runs outward | crowd, raised between t-1 s and t+6 s of the scripted event | 0/10 |
| crowd_positive | sudden_running | A | 10 | a walking group all break into a run | crowd, raised between t-1 s and t+6 s of the scripted event | 0/10 |
| crowd_positive | surge | A | 10 | everyone rushes to one point | crowd, raised between t-1 s and t+6 s of the scripted event | 0/10 |
| crowd_trap | festival_procession | A | 10 | a slow, dancing procession | no crowd incident above Low severity | 5/10 |
| crowd_trap | jogging_group | A | 10 | a jogging group passes | no crowd incident above Low severity | 10/10 |
| crowd_trap | orderly_queue | A | 10 | an orderly queue shuffling forward | no crowd incident above Low severity | 10/10 |
| crowd_trap | running_for_bus | A | 10 | three to five people run for a bus | no crowd incident above Low severity | 10/10 |
| crowd_trap | running_from_rain | A | 10 | people run to a shelter when it starts to rain | no crowd incident above Low severity | 10/10 |
| crowd_trap | train_arrival_rush | A | 10 | a Mumbai local empties onto the platform and everyone walks briskly one way | no crowd incident above Low severity | 4/10 |
| other | fall_alone | A | 10 | a person falls and lies still | medical, raised between t-1 s and t+16 s of the scripted event | 0/10 |
| other | intrusion | A | 10 | a person walks onto a railway track zone | security (intrusion), raised between t-1 s and t+5 s of the scripted event | 10/10 |
| other | loitering | A | 10 | one person stays near a gate for 80 s | security (loiter), raised between t-6 s and t+10 s of the scripted event | 0/10 |
| pixel_accident | demo_accident_ucf010 | B | 12 | real clip demo_accident_ucf010 with condition 'dropped_frames' applied to every frame | accident, raised between t+7.66667 s and t+19 s of the scripted event | 5/12 |
| pixel_baggage | demo_baggage_aboda9 | B | 12 | real clip demo_baggage_aboda9 with condition 'dropped_frames' applied to every frame | baggage | 0/12 |
| pixel_crowd | demo_crowd_umn4 | B | 12 | real clip demo_crowd_umn4 with condition 'dropped_frames' applied to every frame | crowd, raised between t+16.8 s and t+27.7667 s of the scripted event | 7/12 |
| system | crash_and_bag_same_area | A | 10 | a crash on cam1 and a bag on cam2 in the same area: two incidents of different types | accident, raised between t-1 s and t+6 s of the scripted event; plus a baggage incident on the second camera | 6/10 |
| system | low_fps_accident | A | 10 | camera delivers 3 fps | accident, raised between t-1 s and t+6 s of the scripted event | 6/10 |
| system | low_fps_bag | A | 10 | camera delivers 2 fps | baggage, raised between t+7 s and t+30 s of the scripted event | 8/10 |
| system | rtsp_reconnect_accident | A | 10 | the stream drops for 4-8 s just after a crash; must not raise a duplicate | accident, raised between t-1 s and t+6 s of the scripted event, exactly 1 incident(s) | 7/10 |
| system | rtsp_reconnect_bag | A | 10 | the stream drops for 4-8 s while a bag is being left; pipeline resets on reconnect | baggage, raised between t+7 s and t+45 s of the scripted event | 8/10 |
| system | same_incident_2cams | A | 10 | one crash seen by two cameras: one merged incident | accident, raised between t-1 s and t+6 s of the scripted event, exactly 1 incident(s), merged across at least 2 cameras | 5/10 |
| system | same_incident_3cams | A | 10 | one crash seen by three cameras: one merged incident | accident, raised between t-1 s and t+6 s of the scripted event, exactly 1 incident(s), merged across at least 2 cameras | 7/10 |
| system | two_incidents_two_areas | A | 10 | two crashes at the same time in different areas: two incidents | accident, raised between t-1 s and t+6 s of the scripted event, exactly 2 incident(s) | 5/10 |
| traffic_anomaly | pedestrian_on_highway | A | 10 | a person walks onto the carriageway | security (pedestrian), raised between t-1 s and t+8 s of the scripted event | 3/10 |
| traffic_anomaly | stalled_vehicle | A | 10 | a car stops in a live lane for 40 s | security (stalled), raised between t+25 s and t+42 s of the scripted event | 6/10 |
| traffic_anomaly | wrong_way | A | 10 | one car drives against the lane's flow | security (wrong-way), raised between t-1 s and t+5 s of the scripted event | 10/10 |
