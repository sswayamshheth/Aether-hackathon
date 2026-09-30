# DECISIONS.md

Decisions taken without the user, newest last. Format: decision / options / why.

| # | Decision | Options considered | Why |
|---|---|---|---|
| 1 | CPU inference, models exported to OpenVINO | CPU PyTorch, ONNX Runtime, OpenVINO | No NVIDIA GPU (Intel i5-1230U + Iris Xe). OpenVINO is built for this chip. Measured numbers in BENCH.md. |
| 2 | Package caches on E: (`.cache\`) | default cache on C: | C: had 4.7 GB free at start; one torch download could fill it. |
| 3 | ffmpeg 9.0.2 and MediaMTX v1.21.1 as portable builds in `tools\` | winget system install | Stays inside the project folder, no admin rights, removable. |
| 4 | Unlicensed repos: re-implement ideas, never copy files or ship their weights | copy code anyway; skip those repos | All six suggested repos have no licence file (see DISCOVERY.md). Re-implementing keeps the project defensible in front of judges. |
| 5 | One shared reference venv (`_reference\.venv`) instead of one venv per repo | one venv per repo | All five repos need the same stack (torch + ultralytics + opencv). Five copies would cost about 6 GB and 10+ minutes on a machine with under 1.5 GB free RAM. The project venv stays separate, which is what the rule protects. |
| 6 | No subagents, everything runs serially | parallel agents | The machine sits at 24-27 GB of 28 GB commit with the user's other apps running; it crashed from this on 2026-09-28. |
| 7 | The user's running Python apps (ports 8090 etc.) are left alone | stop them to free RAM | Not ours to stop. We work inside the remaining headroom. |
| 8 | Bench clips: first 8 annotated UCF-Crime RoadAccidents test videos by number, 6 ABODA videos, the full UMN video, 4 UCF-Crime normal videos | hand-picked clips | Picking by number avoids cherry-picking. UCF-Crime ships onset frames, UMN ships burnt-in abnormal captions, so delay and frame-level AUC can be measured. |
| 9 | Memory notes under `.claude` are not read or written from here on | keep updating memory | The updated brief forbids touching `.claude` folders. (Two memory notes were read before that instruction arrived.) |
