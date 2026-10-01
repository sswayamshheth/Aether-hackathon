# models/MANIFEST.md

Model files are not in git (`.gitignore`: `models/*.pt`, `models/stable/`, OpenVINO folders, `models/siglip`, `models/violence_vit`). This lists what this machine had on 2026-10-01, with SHA-256, so a copy can be checked. `models/stable/` is the snapshot taken before the overnight run (copied, not moved).

| File | MB | SHA-256 |
|---|---|---|
| `models/accident.pt` | 110 | `ea56e358905e79e1451170e699b21ad774ca95e12034ae1ab1f7d09fd3619cae` |
| `models/candidates/accident_clf.json` | 1 | `0bc30aa7b47fcf73d4b731271c725d9c74203f88131a73c3d2f9d68e261811a6` |
| `models/crowd_tcn.pt` | 1 | `85612b69a1be84e7456b3c4dd7862716372e466c0f186bda92458697a4d77f78` |
| `models/fall.pt` | 6 | `3f56ad30358d5c63bf8dbc0c1299cf68818c3d291dfb10c94107b94110aadd4c` |
| `models/fire_smoke.pt` | 6 | `b91633799ceb052c814b4f8b77a37efc9a40f002d528df97d74463585fa4f28f` |
| `models/siglip/config.json` | 1 | `cd85b3d28829722820bcb89a2cfbb4160e55fd359249a3044da724166a8d9688` |
| `models/siglip/model.safetensors` | 776 | `2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8` |
| `models/siglip/preprocessor_config.json` | 1 | `d11ccb80f15d358a11bdb070e92e2d889005874b7db15823d5f10d9b2533b14a` |
| `models/siglip/special_tokens_map.json` | 1 | `2b6a1ff67a27e0df9ac0c7d93250fc0d87431c7b366b3d5669217104f9088a26` |
| `models/siglip/tokenizer.json` | 3 | `c6e405cb7c670d56636a9402c81023a55bc6c3c53d89cf02b92f5c5005bfe920` |
| `models/siglip/tokenizer_config.json` | 1 | `d6423dae508cc3a129d22ea443841c111832a1a73125b8f25ea8736951698bcb` |
| `models/stable/accident.pt` | 110 | `ea56e358905e79e1451170e699b21ad774ca95e12034ae1ab1f7d09fd3619cae` |
| `models/stable/crowd_tcn.pt` | 1 | `85612b69a1be84e7456b3c4dd7862716372e466c0f186bda92458697a4d77f78` |
| `models/stable/fall.pt` | 6 | `3f56ad30358d5c63bf8dbc0c1299cf68818c3d291dfb10c94107b94110aadd4c` |
| `models/stable/fire_smoke.pt` | 6 | `b91633799ceb052c814b4f8b77a37efc9a40f002d528df97d74463585fa4f28f` |
| `models/stable/weapon.pt` | 6 | `e85b15fe74a16de9ac98562a072a50bffdcda5a7fb6ef4d8594dc7de466ab6b5` |
| `models/stable/yolo11n.pt` | 6 | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| `models/stable/yolo11n_openvino_model/yolo11n.bin` | 10 | `b3b1f9880c83df785a48bcdfcbfce07e6fef37ab078dd9a9d06093767f3ae04d` |
| `models/stable/yolo11n_openvino_model/yolo11n.xml` | 1 | `678fcac7ce55a4c3ef5dfaf788bc2e9f952375b96c42ce657335d4c95dd86479` |
| `models/stable/yolo11s.pt` | 19 | `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5` |
| `models/stable/yolov8n.pt` | 7 | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
| `models/violence_vit/config.json` | 1 | `03652439b83bb9626e74675127b66e0278da16d74660e581a3be48663f75c626` |
| `models/violence_vit/model.safetensors` | 328 | `9eec3237288742eb4267cb2cbbbdacba5bee889be4673215bfe40e1dbd5621a5` |
| `models/violence_vit/preprocessor_config.json` | 1 | `5e6895a8a80efa00a98656b6c24d202d7582614ceea87aa122f861120dc833c0` |
| `models/weapon.pt` | 6 | `e85b15fe74a16de9ac98562a072a50bffdcda5a7fb6ef4d8594dc7de466ab6b5` |
| `models/yolo11n.pt` | 6 | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| `models/yolo11n_openvino_model/yolo11n.bin` | 10 | `b3b1f9880c83df785a48bcdfcbfce07e6fef37ab078dd9a9d06093767f3ae04d` |
| `models/yolo11n_openvino_model/yolo11n.xml` | 1 | `678fcac7ce55a4c3ef5dfaf788bc2e9f952375b96c42ce657335d4c95dd86479` |
| `models/yolo11s.pt` | 19 | `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5` |
| `models/yolov8n.pt` | 7 | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
