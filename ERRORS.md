# ERRORS.md - synthetic suite failure clusters

Source: `docs\results\synthetic_suite_baseline.json` (2026-10-01 06:00), 650 scenarios, 280 failing.
Method A (trajectory-level, models silent): these are logic failures, not vision failures. Real-footage
errors are in docs/results/real_eval*.json and are reported separately.

## Failures by cause

| Cause | Failures |
|---|---|
| missed (suppressed by filter) | 108 |
| missed (rule gap: no candidate) | 88 |
| false alarm (trap) | 66 |
| early / duplicate | 14 |
| late (timing) | 4 |

## Clusters, largest first

| # | Case | Cause | Count | Conditions in the failures | Example |
|---|---|---|---|---|---|
| 1 | crowd_crossing | false alarm (trap) | 10 | occlusion 4, night 3, rain 3, far/small objects 3 | crowd_crossing_01: 1 accident alarm(s), first at 8.0s (collision) |
| 2 | fight | missed (rule gap: no candidate) | 10 | occlusion 4, night 3, rain 3, far/small objects 3 | fight_01: no ['crowd', 'violence'] in [18.8, 27.8]s |
| 3 | loitering | missed (rule gap: no candidate) | 10 | occlusion 4, night 3, rain 3, far/small objects 3 | loitering_01: no security in [58.0, 74.0]s |
| 4 | red_light_queue | false alarm (trap) | 10 | occlusion 4, night 3, rain 3, far/small objects 3 | red_light_queue_01: 1 accident alarm(s), first at 10.0s (collision) |
| 5 | rollover | missed (rule gap: no candidate) | 10 | occlusion 4, night 3, rain 3, far/small objects 3 | rollover_01: no accident in [8.4, 15.4]s |
| 6 | single_vehicle_divider | missed (rule gap: no candidate) | 10 | occlusion 4, night 3, rain 3, far/small objects 3 | single_vehicle_divider_01: no accident in [6.7, 13.7]s |
| 7 | stop_and_go | false alarm (trap) | 10 | occlusion 4, night 3, rain 3, far/small objects 3 | stop_and_go_01: 1 accident alarm(s), first at 4.4s (collision) |
| 8 | surge | missed (rule gap: no candidate) | 10 | occlusion 4, night 3, rain 3, far/small objects 3 | surge_01: harness error |
| 9 | perspective_overlap | false alarm (trap) | 9 | occlusion 4, rain 3, far/small objects 3, clean conditions 2 | perspective_overlap_01: 1 accident alarm(s), first at 9.2s (collision) |
| 10 | collapsed_in_crowd | missed (suppressed by filter) | 8 | occlusion 4, rain 3, far/small objects 3, clean conditions 2 | collapsed_in_crowd_01: no medical in [10.1, 27.1]s |
| 11 | counter_flow | missed (rule gap: no candidate) | 8 | night 3, clean conditions 2, fog 2, far/small objects 2 | counter_flow_01: no crowd in [17.6, 24.6]s |
| 12 | panic_dispersal | missed (rule gap: no candidate) | 8 | night 3, clean conditions 2, fog 2, far/small objects 2 | panic_dispersal_01: no crowd in [16.3, 23.3]s |
| 13 | sudden_running | missed (rule gap: no candidate) | 8 | night 3, clean conditions 2, fog 2, far/small objects 2 | sudden_running_01: no crowd in [15.2, 22.2]s |
| 14 | two_wheeler_skid | missed (suppressed by filter) | 8 | occlusion 4, rain 3, far/small objects 3, clean conditions 2 | two_wheeler_skid_01: no accident in [8.8, 15.8]s |
| 15 | vehicle_hits_pedestrian | missed (suppressed by filter) | 8 | far/small objects 3, occlusion 3, clean conditions 2, night 2 | vehicle_hits_pedestrian_01: no accident in [7.2, 14.2]s |
| 16 | fall_alone | missed (suppressed by filter) | 7 | occlusion 4, rain 3, clean conditions 2, <=3 detections/s 2 | fall_alone_01: no medical in [8.2, 25.2]s |
| 17 | pedestrian_on_highway | early / duplicate | 7 | night 3, clean conditions 2, rain 2, occlusion 2 | pedestrian_on_highway_01: early security at 5.0s (event 7.9s); no security in [6.9, 15.9]s |
| 18 | camera_shake | false alarm (trap) | 6 | shake 6, far/small objects 3, fog 2, occlusion 2 | camera_shake_04: 1 accident alarm(s), first at 12.6s (collision) |
| 19 | train_arrival_rush | false alarm (trap) | 6 | clean conditions 2, far/small objects 2, night 1, rain 1 | train_arrival_rush_01: crowd alarm at Critical severity (overcrowding) at 15.4s |
| 20 | festival_procession | false alarm (trap) | 5 | clean conditions 2, rain 2, occlusion 2, <=3 detections/s 2 | festival_procession_01: crowd alarm at Critical severity (overcrowding) at 4.6s |
| 21 | side_impact | missed (suppressed by filter) | 5 | night 3, occlusion 3, rain 2, <=3 detections/s 1 | side_impact_02: no accident in [8.4, 15.4]s |
| 22 | ambulance_stop | false alarm (trap) | 4 | far/small objects 2, clean conditions 1, fog 1, rain 1 | ambulance_stop_01: 1 accident alarm(s), first at 12.4s (collision) |
| 23 | crash_and_bag_same_area | missed (suppressed by filter) | 4 | rain 3, occlusion 3, night 2, <=3 detections/s 2 | crash_and_bag_same_area_03: no accident in [8.8, 15.8]s |
| 24 | hit_and_run | missed (suppressed by filter) | 4 | fog 2, far/small objects 2, night 1, rain 1 | hit_and_run_04: no accident in [7.7, 14.7]s |
| 25 | low_fps_accident | missed (suppressed by filter) | 4 | <=3 detections/s 4, occlusion 2, far/small objects 2, night 1 | low_fps_accident_02: no accident in [8.0, 15.0]s |
| 26 | same_incident_2cams | missed (suppressed by filter) | 4 | occlusion 3, rain 2, night 2, <=3 detections/s 1 | same_incident_2cams_03: no accident in [7.0, 14.0]s |
| 27 | under_seat | missed (suppressed by filter) | 4 | night 3, fog 2, far/small objects 1, rain 1 | under_seat_02: no baggage in [21.3, 44.3]s |
| 28 | behind_pillar | missed (suppressed by filter) | 3 | night 3, rain 1, occlusion 1, <=3 detections/s 1 | behind_pillar_02: no baggage in [21.9, 44.9]s |
| 29 | dense_crowd | missed (suppressed by filter) | 3 | night 3, rain 1, occlusion 1, <=3 detections/s 1 | dense_crowd_02: no baggage in [21.4, 44.4]s |
| 30 | exit_blocked | missed (suppressed by filter) | 3 | night 2, fog 2, far/small objects 1 | exit_blocked_02: no crowd in [-0.5, 15.5]s |
| 31 | fall_alone | missed (rule gap: no candidate) | 3 | night 2, fog 2, far/small objects 1 | fall_alone_02: no medical in [8.8, 25.8]s |
| 32 | head_on | missed (suppressed by filter) | 3 | rain 2, occlusion 2, <=3 detections/s 2, fog 1 | head_on_04: no accident in [7.8, 14.8]s |
| 33 | mob_gathering | missed (suppressed by filter) | 3 | night 2, occlusion 2, rain 1, <=3 detections/s 1 | mob_gathering_05: no crowd in [11.0, 27.0]s |
| 34 | owner_leaves_view | missed (suppressed by filter) | 3 | night 3, rain 1, occlusion 1, <=3 detections/s 1 | owner_leaves_view_02: no baggage in [23.2, 46.2]s |
| 35 | pileup | early / duplicate | 3 | night 2, rain 1, occlusion 1, <=3 detections/s 1 | pileup_02: early accident at 6.4s (event 10.0s); no accident in [9.0, 16.0]s |
| 36 | rear_end | missed (suppressed by filter) | 3 | occlusion 2, rain 1, far/small objects 1, ID switch 1 | rear_end_03: no accident in [7.9, 14.9]s |
| 37 | rtsp_reconnect_accident | missed (suppressed by filter) | 3 | rain 2, occlusion 2, night 1, fog 1 | rtsp_reconnect_accident_03: no accident in [6.2, 13.2]s |
| 38 | same_incident_3cams | missed (suppressed by filter) | 3 | occlusion 3, rain 2, ID switch 2, far/small objects 1 | same_incident_3cams_03: no accident in [8.0, 15.0]s |
| 39 | stalled_vehicle | missed (rule gap: no candidate) | 3 | far/small objects 2, occlusion 2, ID switch 2, rain 1 | stalled_vehicle_06: no security in [31.8, 48.8]s |
| 40 | taken_by_stranger | missed (suppressed by filter) | 3 | night 3, rain 1, occlusion 1, <=3 detections/s 1 | taken_by_stranger_02: no baggage in [18.5, 41.5]s |
| 41 | two_incidents_two_areas | early / duplicate | 3 | rain 2, occlusion 2, night 1, fog 1 | two_incidents_two_areas_03: 1 accident incidents, expected 2 |
| 42 | bin_box_stroller | false alarm (trap) | 2 | far/small objects 1, occlusion 1, ID switch 1, clean conditions 1 | bin_box_stroller_06: 1 baggage alarm(s), first at 20.8s (unattended) |
| 43 | collapsed_in_crowd | missed (rule gap: no candidate) | 2 | night 2, fog 1 | collapsed_in_crowd_02: no medical in [10.5, 27.5]s |
| 44 | dropped_owner_walks_away | missed (suppressed by filter) | 2 | night 2, rain 1, occlusion 1, <=3 detections/s 1 | dropped_owner_walks_away_05: no baggage in [20.0, 43.0]s |
| 45 | group_bags | missed (suppressed by filter) | 2 | night 2, rain 1, occlusion 1, <=3 detections/s 1 | group_bags_05: no baggage in [23.0, 46.0]s |
| 46 | lane_merge | false alarm (trap) | 2 | rain 1, occlusion 1, clean conditions 1 | lane_merge_03: 1 accident alarm(s), first at 24.2s (collision) |
| 47 | left_on_bench | missed (suppressed by filter) | 2 | night 2, rain 1, occlusion 1, <=3 detections/s 1 | left_on_bench_05: no baggage in [22.0, 45.0]s |
| 48 | low_fps_bag | missed (suppressed by filter) | 2 | night 2, <=3 detections/s 2, rain 1, occlusion 1 | low_fps_bag_05: no baggage in [23.0, 46.0]s |
| 49 | overcrowding | missed (suppressed by filter) | 2 | night 1, far/small objects 1, occlusion 1, ID switch 1 | overcrowding_02: no crowd in [-0.5, 15.5]s |
| 50 | panic_dispersal | missed (suppressed by filter) | 2 | occlusion 2, rain 1, far/small objects 1, ID switch 1 | panic_dispersal_03: no crowd in [19.0, 26.0]s |
| 51 | restricted_zone | missed (suppressed by filter) | 2 | night 2, rain 1, occlusion 1, <=3 detections/s 1 | restricted_zone_05: no baggage in [21.0, 44.0]s |
| 52 | rtsp_reconnect_bag | missed (suppressed by filter) | 2 | night 2, rain 1, occlusion 1, <=3 detections/s 1 | rtsp_reconnect_bag_05: no baggage in [19.1, 57.1]s |
| 53 | sudden_running | missed (suppressed by filter) | 2 | occlusion 2, rain 1, far/small objects 1, ID switch 1 | sudden_running_03: no crowd in [17.5, 24.5]s |
| 54 | two_incidents_two_areas | missed (suppressed by filter) | 2 | occlusion 2, night 1, rain 1, <=3 detections/s 1 | two_incidents_two_areas_05: no accident in [6.9, 13.9]s |
| 55 | two_wheeler_skid | missed (rule gap: no candidate) | 2 | night 2, fog 1 | two_wheeler_skid_02: no accident in [8.4, 15.4]s |
| 56 | u_turn | false alarm (trap) | 2 | rain 1, occlusion 1, clean conditions 1 | u_turn_03: 1 accident alarm(s), first at 7.0s (collision) |
| 57 | vehicle_hits_pedestrian | missed (rule gap: no candidate) | 2 | rain 1, occlusion 1, night 1, fog 1 | vehicle_hits_pedestrian_03: no accident in [6.4, 13.4]s |
| 58 | crush_buildup | late (timing) | 1 | night 1, rain 1, occlusion 1, <=3 detections/s 1 | crush_buildup_05: no crowd in [31.1, 44.1]s, late at 44.4s |
| 59 | crush_buildup | missed (suppressed by filter) | 1 | night 1, fog 1 | crush_buildup_08: no crowd in [32.4, 45.4]s |
| 60 | crush_buildup | early / duplicate | 1 | far/small objects 1, shake 1 | crush_buildup_10: early crowd at 33.4s (event 35.0s); no crowd in [34.0, 47.0]s |
| 61 | left_on_bench | late (timing) | 1 | night 1 | left_on_bench_02: no baggage in [18.4, 41.4]s, late at 47.4s |
| 62 | overcrowding | late (timing) | 1 | night 1, fog 1 | overcrowding_08: no crowd in [-0.5, 15.5]s, late at 16.8s |
| 63 | rear_end | missed (rule gap: no candidate) | 1 | night 1, rain 1, occlusion 1, <=3 detections/s 1 | rear_end_05: no accident in [6.8, 13.8]s |
| 64 | same_incident_2cams | missed (rule gap: no candidate) | 1 | rain 1, occlusion 1, ID switch 1, <=3 detections/s 1 | same_incident_2cams_09: no accident in [8.2, 15.2]s |
| 65 | stalled_vehicle | missed (suppressed by filter) | 1 | clean conditions 1 | stalled_vehicle_07: no security in [31.8, 48.8]s |
| 66 | under_seat | late (timing) | 1 | rain 1, occlusion 1, ID switch 1, <=3 detections/s 1 | under_seat_09: no baggage in [22.2, 45.2]s, late at 49.5s |
