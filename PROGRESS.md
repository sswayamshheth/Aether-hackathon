# PROGRESS.md - Drishti (Team HCQ_D36, HackConquest PS 06)

Live checklist. Status: TODO / DOING / DONE / PARTIAL / CUT. If context is lost, read this,
then DECISIONS.md and STATUS.md.

| Phase | Task | Status | Notes |
|---|---|---|---|
| 0 | Environment check -> ENV.md | DONE | CPU only, low RAM, portable ffmpeg + MediaMTX in `tools\` |
| 1 | Repo discovery -> DISCOVERY.md | DONE | all six suggested repos have no licence file |
| 1 | Shared bench set in `data\bench\` | DONE | 8 accident, 6 baggage, 11 crowd scenes, 4 normal |
| 1 | Run and compare 5 repos + 1 HF model -> BENCH.md | DONE | one repo BROKEN as cloned (missing dependency), fixed with one pin |
| 1 | Hybrid plan | DONE | in BENCH.md and on the Models page |
| 2 | Scaffold, git, .env.example, DECISIONS, CREDITS | DONE | |
| 3 | Ingestion: RTSP with reconnect, file upload, ring buffer | DONE | |
| 3 | RTSP simulation (MediaMTX + ffmpeg) | DONE | `scripts\simulate_rtsp.ps1`, verified with ffprobe |
| 3 | YOLO11n OpenVINO + ByteTrack, per-camera FPS and latency | DONE | |
| 3 | Frames to browser | DONE | one binary WebSocket for all cameras; MJPEG endpoint as fallback |
| 3 | Milestone: 4 RTSP cameras + upload with boxes and IDs | DONE | 4 RTSP cameras verified live; upload path verified by API test |
| 4 | Accident model | DONE | MIT YOLO11x weights; weak on this footage, see BENCH.md |
| 4 | Crowd model (temporal CNN on UMN) | DONE | `docs/results/crowd_model.json` |
| 4 | Baggage (COCO bags + owner logic) | PARTIAL | logic tested; COCO bag detection is the limit |
| 4 | Kaggle fine-tunes | PARTIAL | notebooks written, not run (no Kaggle token, no Roboflow key) |
| 4 | M4 learned severity scorer | CUT | rule-based severity with reasons ships instead |
| 5 | False-alarm filter | DONE | persistence, gate, ignore zones, camera agreement |
| 5 | Severity with reasons | DONE | |
| 5 | Cross-camera merge | DONE | by area + time window; verified live on cam1 + cam2 |
| 5 | SQLite incidents, keyframe, evidence clip | DONE | |
| 5 | WebSocket alerts, Telegram behind flag | DONE | Telegram never sent for real (no token) |
| 5 | Vision verification behind flag | PARTIAL | built, fails safe with a bad key; never ran with a real key |
| 5 | Operator feedback moves the gate | DONE | |
| 5 | Re-ID (boxmot/OSNet) | CUT | nice-to-have |
| 6 | Dashboard: command, incident, cameras, zones, analytics, models | DONE | |
| 6 | Screenshot review in Chrome at 1440 and 1920 | DONE | three rounds; final set in `docs\screenshots\`; 11 interaction checks pass |
| 6 | Light theme | CUT | nice-to-have |
| 6 | WebRTC | CUT | nice-to-have |
| 7 | Demo mode (cached detections) | DONE | `scripts\demo.ps1` |
| 7 | start.ps1 / demo.ps1 / stop.ps1 | DONE | both tested from PowerShell |
| 7 | Backend tests | DONE | 27 passing |
| 7 | End-to-end eval, with and without filter | DONE | accident 1/8, crowd 10/11, baggage 3/6; see BENCH.md |
| 8 | README, CREDITS, WHAT_WE_BUILT | DONE | |
| 8 | PITCH_NOTES, STATUS | DONE | |
