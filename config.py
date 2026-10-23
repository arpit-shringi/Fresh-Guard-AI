# config.py: SINGLE SOURCE OF TRUTH FOR PATHS, THRESHOLDS & SLM SETTINGS
# Every path is resolved relative to THIS file, so the app works no matter which
# directory you launch `streamlit run` or `python` from.
# Any value can be overridden with an environment variable
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
APP_VERSION = "v6 (2026-10-21, INR)"   # shown in the dashboard sidebar


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader (KEY=VALUE per line) so the Groq key can live in a file
    instead of a Windows environment variable. Real env vars always win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


_load_dotenv(PROJECT_ROOT / ".env")

# Model weights (expected in the project root, next to this file)
#   Stage 1  object detector       -> sku110k_yolo.pt
#   Stage 2A fruit/veg classifier  -> vgg.h5
#   Stage 2B ripeness classifier   -> freshguard_4class_ripeness_20ep.pt
# Rename here (only here) if your files are called something else.
WEIGHTS_DIR = Path(os.getenv("FRESHGUARD_WEIGHTS_DIR", PROJECT_ROOT))
DETECTOR_WEIGHTS = WEIGHTS_DIR / "sku110k_yolo.pt"
DETECTOR_FALLBACK_WEIGHTS = WEIGHTS_DIR / "yolo11s.pt"
PRODUCE_WEIGHTS = WEIGHTS_DIR / "vgg.h5"
RIPENESS_WEIGHTS = WEIGHTS_DIR / "freshguard_4class_ripeness_20ep.pt"
SKU_NANO_URL = "https://huggingface.co/jz67/localfirst-vision-yolo/resolve/main/sku110k-yolov8n.pt"

# Optional faster YOLO runtime: `python optimize_models.py` exports both YOLO models
# to OpenVINO folders and benchmarks them on your machine; enable with FRESHGUARD_USE_FAST_MODELS=1
# only if the benchmark shows a gain (it is CPU-dependent).
DETECTOR_FAST = WEIGHTS_DIR / "sku110k_yolo_openvino_model"
RIPENESS_FAST = WEIGHTS_DIR / "freshguard_4class_ripeness_20ep_openvino_model"
USE_FAST_MODELS = os.getenv("FRESHGUARD_USE_FAST_MODELS", "0") == "1"   # opt-in: benchmark first

# Speed settings
#   PRELOAD_MODELS        load + warm up the 3 models in the background when the
#                         dashboard first opens (instead of on the first click)
#   PARALLEL_CLASSIFIERS  run the produce (VGG) and ripeness (YOLO-cls) classifiers
#                         at the same time; both only need the crops
#   SCAN_CACHE_SIZE       repeat scans of the same photo reuse the vision result
PRELOAD_MODELS = os.getenv("FRESHGUARD_PRELOAD", "1") == "1"
PARALLEL_CLASSIFIERS = os.getenv("FRESHGUARD_PARALLEL", "1") == "1"
SCAN_CACHE_SIZE = 16
DISPLAY_MAX_PX = 1100   # uploaded photo is downscaled to this for display only

# Vision pipeline settings
DETECTOR_CONF = 0.15          # Stage 1 box confidence
DETECTOR_IOU = 0.45
DETECTOR_MAX_DET = 300
MIN_CROP_SIDE_PX = 15         # crops <= this many px on either side are dropped
MIN_PRODUCE_CONF = float(os.getenv("FRESHGUARD_MIN_PRODUCE_CONF", 0.35))  # Stage 2A softmax floor
BATCH_SIZE = 32

# Database
DB_PATH = Path(os.getenv("FRESHGUARD_DB_PATH", PROJECT_ROOT / "supermarket_meta.db"))

# Decision matrix threshold
OVERRIPE_ALERT_PCT = 15.0
RIPE_PEAK_PCT = 60.0
UNRIPE_HOLD_PCT = 50.0
RI_DETERIORATING = 0.65
RI_UNRIPE = 0.35
CURRENCY = os.getenv("FRESHGUARD_CURRENCY", "₹")           # symbol shown in the UI and copy
CURRENCY_CODE = os.getenv("FRESHGUARD_CURRENCY_CODE", "INR")  # stored in the DB; mismatch -> reseed


def money(x: float) -> str:
    """₹36 for whole amounts, ₹17.50 otherwise (Indian retail style)."""
    x = round(float(x), 2)
    return f"{CURRENCY}{x:,.0f}" if x == int(x) else f"{CURRENCY}{x:,.2f}"

# Copy generation: Groq SLM only. Needs GROQ_API_KEY (put it in .env).
#   qwen/qwen3.8-27b (Alibaba Qwen, Preview)  ->  meta-models/muse-spark-open (Meta)
# Override with FRESHGUARD_GROQ_MODELS="model-a,model-b".
# If Groq is unreachable (no key / no internet), the dashboard shows a warning and
# uses the built-in offline copy so a live demo never crashes 
SLM_BACKEND = "groq"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODELS = [m.strip() for m in os.getenv(
    "FRESHGUARD_GROQ_MODELS", "qwen/qwen3.8-27b,meta-models/muse-spark-open").split(",") if m.strip()]
GROQ_MODEL = GROQ_MODELS[0]
GROQ_TIMEOUT_S = float(os.getenv("FRESHGUARD_GROQ_TIMEOUT", 30))

# Hidden demo safety net (no UI switch): FRESHGUARD_SAMPLE_MODE=1 skips the vision
# models and uses the hand-counted pic.png inventory.
USE_SAMPLE_INVENTORY = os.getenv("FRESHGUARD_SAMPLE_MODE", "0") == "1"

# Runtime folders
UPLOAD_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Hand-counted inventory for sample_data/pic.png
GROUND_TRUTH_PATH = PROJECT_ROOT / "sample_data" / "pic_inventory.json"
