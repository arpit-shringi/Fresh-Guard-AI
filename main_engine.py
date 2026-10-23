
# main_engine.py: VALIDATED 3-MODEL INVENTORY & RIPENESS ENGINE
# # Stage 1  : YOLOv8n (SKU-110K)         -> bounding boxes
# Stage 2A : Keras VGG-16 (vgg.h5)      -> produce type (36 classes)
# Stage 2B : YOLOv8-Cls (ripeness .pt)  -> Ripe / Unripe / Overripe / Rotten
# Stage 3  : aggregate into the inventory dict contract (CLAUDE.md §3A)
#
# Changes vs. previous version:
#   * Import-time pip auto-installer removed (it reinstalled OpenCV on EVERY
#     import because `__import__("opencv")` always fails). Use requirements.txt.
#   * TensorFlow / Ultralytics are imported lazily, so importing this module
#     (e.g. from Streamlit) is instant, and models can be injected for tests.
#   * Low-confidence produce predictions are dropped instead of silently becoming
#     a phantom product line (the detector also boxes bin edges, leaves, etc.).
#   * Ripeness labels are normalised ("over_ripe", "OverRipe" -> "Overripe").
# import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

import config

# 36-Class mapping from the akshwin Fruit_Vegetable_Classification repository
PRODUCE_CLASSES_36 = {
    0: "Apple", 1: "Banana", 2: "Beetroot", 3: "Bell Pepper", 4: "Cabbage",
    5: "Capsicum", 6: "Carrot", 7: "Cauliflower", 8: "Chilli Pepper", 9: "Corn",
    10: "Cucumber", 11: "Eggplant", 12: "Garlic", 13: "Ginger", 14: "Grapes",
    15: "Jalepeno", 16: "Kiwi", 17: "Lemon", 18: "Lettuce", 19: "Mango",
    20: "Onion", 21: "Orange", 22: "Paprika", 23: "Pear", 24: "Peas",
    25: "Pineapple", 26: "Pomegranate", 27: "Potato", 28: "Raddish", 29: "Soy Beans",
    30: "Spinach", 31: "Sweetcorn", 32: "Sweetpotato", 33: "Tomato", 34: "Turnip",
    35: "Watermelon"
}

FRUIT_SET = {
    "Apple", "Banana", "Grapes", "Kiwi", "Lemon", "Mango",
    "Orange", "Pear", "Pineapple", "Pomegranate", "Watermelon"
}

RIPENESS_STAGES = ("Ripe", "Unripe", "Overripe", "Rotten")
_RIPENESS_LOOKUP = {s.lower(): s for s in RIPENESS_STAGES}


def normalize_ripeness_label(label: str) -> Optional[str]:
    """Map raw classifier label -> one of RIPENESS_STAGES, or None if unrecognised."""
    key = re.sub(r"[^a-z]", "", str(label).lower())
    return _RIPENESS_LOOKUP.get(key)


# MODEL WEIGHT FILES (paths come from config.py; files live in the project root)
WEIGHT_FILES = {
    "Stage 1  object detector (YOLO, SKU-110K)": config.DETECTOR_WEIGHTS,       # sku110k_yolo.pt
    "Stage 2A fruit/vegetable classifier (VGG16)": config.PRODUCE_WEIGHTS,      # vgg.h5
    "Stage 2B ripeness classifier (YOLO-cls)": config.RIPENESS_WEIGHTS,         # freshguard_4class_ripeness_20ep.pt
}


def weight_file_report() -> str:
    """One line per weight file: found / MISSING, with the full path."""
    return "\n".join(f"  [{'found' if p.exists() else 'MISSING'}] {name}: {p}" for name, p in WEIGHT_FILES.items())


def _load_keras_h5(path: Path, tf):
    """Load vgg.h5. Keras 3 (TF >= 2.16) cannot read some Keras-2 .h5 files; in that
    case retry with the legacy `tf_keras` package (pip install tf-keras)."""
    try:
        return tf.keras.models.load_model(str(path), compile=False)
    except Exception as keras3_error:
        try:
            import tf_keras
        except ImportError:
            raise RuntimeError(f"Could not load '{path.name}' with Keras 3 ({keras3_error}). "
                               f"Run `pip install tf-keras` and try again.") from keras3_error
        print(f"  -> Keras 3 could not read '{path.name}'; loading with legacy tf_keras instead.")
        return tf_keras.models.load_model(str(path), compile=False)


def _load_yolo(pt_path: Path, fast_dir: Path, task: str):
    """YOLO from the .pt file, or from its OpenVINO export when enabled and present."""
    from ultralytics import YOLO
    if config.USE_FAST_MODELS and fast_dir.exists():
        print(f"  -> Using optimized OpenVINO model: {fast_dir.name}")
        return YOLO(str(fast_dir), task=task)
    return YOLO(str(pt_path))


def empty_inventory_row(produce_name: str) -> dict:
    return {
        "Product_Type": produce_name,
        "Product_Count": 0,
        "Ripe_Count": 0,
        "Unripe_Count": 0,
        "Overripe_Count": 0,
        "Rotten_Count": 0,
    }


class ShelfInventoryPipeline:
    def __init__(
        self,
        detector_path: str = str(config.DETECTOR_WEIGHTS),
        produce_path: str = str(config.PRODUCE_WEIGHTS),
        ripeness_path: str = str(config.RIPENESS_WEIGHTS),
        batch_size: int = config.BATCH_SIZE,
        min_produce_conf: float = config.MIN_PRODUCE_CONF,
        *,
        detector_model=None,
        produce_model=None,
        ripeness_model=None,
    ):
        """
        Pass pre-built `detector_model` / `produce_model` / `ripeness_model` objects
        to skip loading weights from disk (used by the test-suite).
        """
        self.batch_size = batch_size
        self.min_produce_conf = min_produce_conf
        self.last_run_stats: dict = {}
        self.parallel = config.PARALLEL_CLASSIFIERS
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fg-classify")

        if detector_model and produce_model and ripeness_model:
            self.detector_model = detector_model
            self.produce_model = produce_model
            self.ripeness_model = ripeness_model
            return

        print("[1/3] Booting 3-Model Pipeline...")
        print(weight_file_report())
        missing = [p.name for p in (Path(produce_path), Path(ripeness_path)) if not p.exists()]
        if missing:   # fail early with ONE clear message instead of after a slow TF import
            raise FileNotFoundError(f"Missing model weight file(s) {missing} in {Path(produce_path).parent}. "
                                    f"Copy them next to streamlit_app.py or set FRESHGUARD_WEIGHTS_DIR.")
        import tensorflow as tf            # lazy: heavy import
        from ultralytics import YOLO       # lazy: heavy import

        # Prevent TensorFlow from hogging 100% of GPU VRAM so PyTorch (YOLO) can run alongside it
        for gpu in tf.config.list_physical_devices("GPU"):
            try:
                tf.config.experimental.set_memory_growth(gpu, True)
            except RuntimeError:
                pass  # already initialised

        # 1. Stage 1 Detector (download once if missing, else fall back)
        det_file = Path(detector_path)
        if not det_file.exists():
            print(f"  -> '{det_file.name}' not found locally. Attempting download (~6 MB)...")
            try:
                urllib.request.urlretrieve(config.SKU_NANO_URL, str(det_file))
                print(f"  -> Downloaded '{det_file.name}' successfully.")
            except Exception as e:
                det_file = config.DETECTOR_FALLBACK_WEIGHTS
                print(f"  -> Download failed ({e}). Falling back to '{det_file.name}'.")
        self.detector_model = _load_yolo(det_file, config.DETECTOR_FAST, "detect")

        # 2. Stage 2A Produce Classifier
        self.produce_model = _load_keras_h5(Path(produce_path), tf)

        # 3. Stage 2B Ripeness Classifier
        self.ripeness_model = _load_yolo(Path(ripeness_path), config.RIPENESS_FAST, "classify")
        print(f"  -> Ripeness classes: {self.ripeness_model.names}")

    # --------------------------------------------------------------------------
    def _extract_crops(self, image_bgr: np.ndarray, conf_threshold: float) -> list:
        h, w = image_bgr.shape[:2]
        det_results = self.detector_model.predict(
            source=image_bgr, conf=conf_threshold, iou=config.DETECTOR_IOU,
            max_det=config.DETECTOR_MAX_DET, verbose=False
        )[0]

        crops = []
        if det_results.boxes is not None:
            for box in det_results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if (x2 - x1) > config.MIN_CROP_SIDE_PX and (y2 - y1) > config.MIN_CROP_SIDE_PX:
                    crops.append(image_bgr[y1:y2, x1:x2].copy())
        return crops

    def _classify_produce(self, crops_bgr: list):
        """Stage 2A: VGG16 on RGB 224x224 crops scaled to [0,1]. Uses predict_on_batch per chunk
        (no tf.data pipeline per call, which Keras' predict() builds every time)."""
        t0 = time.perf_counter()
        batch = np.stack([cv2.resize(cv2.cvtColor(c, cv2.COLOR_BGR2RGB), (224, 224),
                                     interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
                          for c in crops_bgr], axis=0)
        if hasattr(self.produce_model, "predict_on_batch"):
            preds = np.concatenate([np.asarray(self.produce_model.predict_on_batch(batch[i: i + self.batch_size]))
                                    for i in range(0, len(batch), self.batch_size)], axis=0)
        else:
            preds = np.asarray(self.produce_model.predict(batch, batch_size=self.batch_size, verbose=0))
        return preds, round(time.perf_counter() - t0, 3)

    def _classify_ripeness(self, crops_bgr: list):
        """Stage 2B: YOLO-cls. Ultralytics ignores `batch=` for a list of arrays, so chunk manually."""
        t0 = time.perf_counter()
        preds = []
        for i in range(0, len(crops_bgr), self.batch_size):
            preds.extend(self.ripeness_model.predict(source=crops_bgr[i: i + self.batch_size], imgsz=224, verbose=False))
        return preds, round(time.perf_counter() - t0, 3)

    def warmup(self) -> float:
        """One dummy pass through all 3 models so the first real scan does not pay for
        graph building / predictor setup. Returns seconds taken."""
        t0 = time.perf_counter()
        dummy = np.full((640, 640, 3), 127, dtype=np.uint8)
        self.detector_model.predict(source=dummy, conf=config.DETECTOR_CONF, verbose=False)
        crops = [np.full((224, 224, 3), 127, dtype=np.uint8)] * 2
        self._classify_produce(crops)
        self._classify_ripeness(crops)
        took = round(time.perf_counter() - t0, 3)
        print(f"  -> Models warmed up in {took}s")
        return took

    def process_shelf_image(self, image_path: str, conf_threshold: float = config.DETECTOR_CONF) -> dict:
        """
        Detects all items on the shelf, classifies produce type and ripeness in
        memory-safe batches, and returns the inventory dictionary (CLAUDE.md §3A).
        Run diagnostics are stored on `self.last_run_stats`.
        """
        img_path = Path(image_path)
        # cv2.imread returns None for non-ASCII paths on Windows (e.g. OneDrive folders
        # with accented user names); decoding from raw bytes works everywhere.
        try:
            image_bgr = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        except (OSError, ValueError):
            image_bgr = None
        if image_bgr is None:
            raise ValueError(f"Could not read image at {img_path.resolve()}")

        print(f"[2/3] Extracting bounding boxes from '{img_path.name}'...")
        t0 = time.perf_counter()
        crops_bgr = self._extract_crops(image_bgr, conf_threshold)
        timings = {"detect": round(time.perf_counter() - t0, 3)}

        stats = {"detected_boxes": len(crops_bgr), "classified": 0,
                 "dropped_low_confidence": 0, "unknown_ripeness_labels": 0, "timings_s": timings}
        self.last_run_stats = stats

        inventory: dict = {}
        if not crops_bgr:
            print("  -> No items detected on the shelf.")
            return inventory

        total_items = len(crops_bgr)
        print(f"[3/3] Classifying {total_items} items via VGG16 and YOLO-Cls (batch_size={self.batch_size})...")

        # --- Stage 2A + 2B: both classifiers only need the crops, so they run at the
        # same time (TensorFlow and PyTorch release the GIL during inference).
        t0 = time.perf_counter()
        if self.parallel:
            f_produce = self._executor.submit(self._classify_produce, crops_bgr)
            f_ripe = self._executor.submit(self._classify_ripeness, crops_bgr)
            (vgg_preds, t_vgg), (ripeness_preds, t_ripe) = f_produce.result(), f_ripe.result()
        else:
            vgg_preds, t_vgg = self._classify_produce(crops_bgr)
            ripeness_preds, t_ripe = self._classify_ripeness(crops_bgr)
        timings.update(classify_produce=t_vgg, classify_ripeness=t_ripe,
                       classify_total=round(time.perf_counter() - t0, 3))

        # --- Stage 3: Aggregate into dictionary schema ---
        for vgg_prob, ripe_res in zip(vgg_preds, ripeness_preds):
            cls_idx = int(np.argmax(vgg_prob))
            if float(vgg_prob[cls_idx]) < self.min_produce_conf:
                stats["dropped_low_confidence"] += 1
                continue
            produce_name = PRODUCE_CLASSES_36.get(cls_idx, "Unknown")

            top1_idx = int(ripe_res.probs.top1)
            ripeness_stage = normalize_ripeness_label(ripe_res.names[top1_idx])

            row = inventory.setdefault(produce_name, empty_inventory_row(produce_name))
            row["Product_Count"] += 1
            stats["classified"] += 1
            if ripeness_stage is None:
                stats["unknown_ripeness_labels"] += 1
            else:
                row[f"{ripeness_stage}_Count"] += 1

        if stats["unknown_ripeness_labels"]:
            print(f"  -> WARNING: {stats['unknown_ripeness_labels']} crops had an unrecognised ripeness label. "
                  f"Model names: {getattr(self.ripeness_model, 'names', '?')}")
        print(f"  -> Done: {stats}")
        return inventory


if __name__ == "__main__":
    print("Weight files:\n" + weight_file_report())
    pipeline = ShelfInventoryPipeline()
    test_image = config.PROJECT_ROOT / "sample_data" / "pic.png"
    if test_image.exists():
        print("\nFINAL DICTIONARY OUTPUT:")
        print(json.dumps(pipeline.process_shelf_image(str(test_image)), indent=4))
    else:
        print(f"\nReady! Place a test image at '{test_image}'.")
