# optimize_models.py: OPTIONAL — export both YOLO models to OpenVINO and benchmark
#   python optimize_models.py            # export + benchmark on sample_data/pic.png
# OpenVINO is often faster than PyTorch on Intel CPUs, but not always (it depends
# on the CPU and the model). This script measures BOTH on your machine and tells
# you whether to switch. To switch, add to .env:   FRESHGUARD_USE_FAST_MODELS=1
# Requires: pip install openvino
import sys
import time

import cv2
import numpy as np

import config


def bench(fn, runs: int = 5) -> float:
    fn()                                            # warm-up run, not timed
    t0 = time.perf_counter()
    for _ in range(runs):
        fn()
    return (time.perf_counter() - t0) / runs


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        import openvino
    except ImportError:
        print("openvino is not installed. Run:  pip install openvino")
        return 1
    from ultralytics import YOLO

    jobs = [(config.DETECTOR_WEIGHTS, config.DETECTOR_FAST, 640, "detect"),
            (config.RIPENESS_WEIGHTS, config.RIPENESS_FAST, 224, "classify")]
    for pt, fast, imgsz, _ in jobs:
        if not pt.exists():
            print(f"Missing {pt.name}; copy the weights into the project folder first.")
            return 1
        print(f"Exporting {pt.name} -> {fast.name} ...")
        YOLO(str(pt)).export(format="openvino", imgsz=imgsz, dynamic=True, verbose=False)

    pic = config.PROJECT_ROOT / "sample_data" / "pic.png"
    image = cv2.imdecode(np.fromfile(str(pic), dtype=np.uint8), cv2.IMREAD_COLOR)
    det_pt, det_ov = YOLO(str(config.DETECTOR_WEIGHTS)), YOLO(str(config.DETECTOR_FAST), task="detect")
    boxes = det_pt.predict(image, conf=config.DETECTOR_CONF, verbose=False)[0].boxes
    crops = [image[int(y1):int(y2), int(x1):int(x2)] for x1, y1, x2, y2 in boxes.xyxy.tolist()][:32] \
        or [image[:224, :224]] * 8
    cls_pt, cls_ov = YOLO(str(config.RIPENESS_WEIGHTS)), YOLO(str(config.RIPENESS_FAST), task="classify")

    rows = [("Detector (whole photo)",
             bench(lambda: det_pt.predict(image, conf=config.DETECTOR_CONF, verbose=False)),
             bench(lambda: det_ov.predict(image, conf=config.DETECTOR_CONF, verbose=False))),
            (f"Ripeness ({len(crops)} crops)",
             bench(lambda: cls_pt.predict(source=crops, imgsz=224, verbose=False)),
             bench(lambda: cls_ov.predict(source=crops, imgsz=224, verbose=False)))]
    print(f"\n{'Model':<26}{'PyTorch':>10}{'OpenVINO':>10}")
    for name, t_pt, t_ov in rows:
        print(f"{name:<26}{t_pt:>9.3f}s{t_ov:>9.3f}s")
    gain = sum(r[1] for r in rows) - sum(r[2] for r in rows)
    if gain > 0:
        print(f"\nOpenVINO saves about {gain:.2f}s per scan here. Add FRESHGUARD_USE_FAST_MODELS=1 to .env.")
    else:
        print("\nOpenVINO is not faster on this machine. Keep the default (.pt) models.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
