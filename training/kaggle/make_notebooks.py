"""Writes the two Kaggle notebooks (accident_yolo11n.ipynb, luggage_yolo11n.ipynb).

    python training\\kaggle\\make_notebooks.py

Both fine-tune YOLO11n on a public Roboflow Universe dataset. They need a free Roboflow
API key stored as a Kaggle secret named ROBOFLOW_API_KEY. Neither has been run yet: no
Kaggle token or Roboflow key was available when the project was built.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent


def notebook(title: str, intro: str, workspace: str, project: str, version: int, out_name: str,
             epochs: int, after: str) -> dict:
    def md(text: str) -> dict:
        return {"cell_type": "markdown", "metadata": {}, "source": text}

    def code(text: str) -> dict:
        return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text}

    return {
        "cells": [
            md(f"# {title}\n\n{intro}\n\n**Before running:** Settings -> Accelerator -> GPU T4, Internet on, and add a "
               "Kaggle secret `ROBOFLOW_API_KEY` (Add-ons -> Secrets)."),
            code("!pip -q install ultralytics==8.4.168 roboflow"),
            code("from kaggle_secrets import UserSecretsClient\nfrom roboflow import Roboflow\n\n"
                 "rf = Roboflow(api_key=UserSecretsClient().get_secret('ROBOFLOW_API_KEY'))\n"
                 f"ds = rf.workspace('{workspace}').project('{project}').version({version}).download('yolov11')\n"
                 "print(ds.location)"),
            code("from ultralytics import YOLO\n\nmodel = YOLO('yolo11n.pt')\n"
                 f"model.train(data=f'{{ds.location}}/data.yaml', epochs={epochs}, imgsz=640, batch=32, patience=15,\n"
                 "            project='runs', name='drishti', seed=0)"),
            md("## Held-out metrics\n\nRuns on the dataset's **test** split, which training never saw. "
               "Copy `metrics.json` into `docs/results/` in the repo."),
            code("import json\n\nbest = YOLO('runs/drishti/weights/best.pt')\n"
                 "m = best.val(data=f'{ds.location}/data.yaml', split='test', imgsz=640)\n"
                 "metrics = {'dataset': '" + f"{workspace}/{project} v{version}" + "', 'split': 'test',\n"
                 "           'map50': float(m.box.map50), 'map50_95': float(m.box.map),\n"
                 "           'precision': float(m.box.mp), 'recall': float(m.box.mr),\n"
                 "           'classes': best.names, 'images': int(m.seen) if hasattr(m, 'seen') else None}\n"
                 f"json.dump(metrics, open('{out_name}_metrics.json', 'w'), indent=1)\nmetrics"),
            code(f"import shutil\nshutil.copy('runs/drishti/weights/best.pt', '{out_name}.pt')\n"
                 f"print('Download {out_name}.pt and {out_name}_metrics.json from the Output panel')"),
            md(after),
        ],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}},
        "nbformat": 4, "nbformat_minor": 5,
    }


def main() -> None:
    acc = notebook(
        "Drishti M1: accident detector (YOLO11n)",
        "Fine-tunes YOLO11n on the Roboflow Universe dataset `ann-qwhjm/accident-detection-cwbvs` v2 "
        "(classes accident / moderate / severe; the dataset's own `data.yaml` states CC BY 4.0). "
        "Goal: our own nano-size accident weights, so the project does not depend on an unlicensed `.pt`.",
        "ann-qwhjm", "accident-detection-cwbvs", 2, "accident", 80,
        "## Using the weights\n\n1. Put `accident.pt` in the repo's `models/` folder (replacing the current one).\n"
        "2. Run `backend\\.venv\\Scripts\\python training\\bench\\run_bench.py accident_weights ours_yolo11n models\\accident.pt`\n"
        "   then `training\\bench\\summarise.py ours_yolo11n` and compare with BENCH.md.\n"
        "3. Keep the new weights only if they beat the current model on our clips. Then rerun "
        "`training\\eval_e2e.py`, `training\\prepare_demo.py` and `training\\bench\\make_summary.py`.")
    lug = notebook(
        "Drishti M3: luggage detector (YOLO11n)",
        "Fine-tunes YOLO11n on `guns-detection-cvwjs/luggagedataset-24pgo` (backpack / bag / trolley, 29,053 images; "
        "the authors' README states MIT). Goal: a bag detector that sees parked luggage on CCTV, where COCO "
        "weights found a bag in only about a quarter of ABODA frames (BENCH.md).",
        "guns-detection-cvwjs", "luggagedataset-24pgo", 1, "luggage", 60,
        "## Using the weights\n\nThe pipeline currently takes bags from the shared COCO detector. To use these weights, "
        "bench them first with `run_bench.py bag_detectors` (add the file to the `cands` dict), and wire them in as a "
        "second detector in `backend/app/detector.py` only if they beat COCO on the ABODA clips. "
        "Check the dataset version number on Roboflow Universe before running; version 1 is assumed here.")
    (HERE / "accident_yolo11n.ipynb").write_text(json.dumps(acc, indent=1))
    (HERE / "luggage_yolo11n.ipynb").write_text(json.dumps(lug, indent=1))
    print("wrote accident_yolo11n.ipynb, luggage_yolo11n.ipynb")


if __name__ == "__main__":
    main()
