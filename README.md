# FreshGuard AI — Retail Shelf Intelligence & Dynamic Pricing

Shelf image ➔ 3 vision models ➔ decision matrix (pricing math) ➔ SLM copy ➔ Streamlit dashboard.

## Folder

```
freshguard_ai/
├── streamlit_app.py      # white/green dashboard (5 tabs, approve → outputs/approved_promotions.json)
├── .streamlit/config.toml # theme
├── slm_engine.py         # SLMEngine: Groq SLM copy (offline backup text if Groq is unreachable)
├── decision_engine.py    # DecisionEngine: scenarios A–D, markdown math, 1 batched DB call
├── main_engine.py        # ShelfInventoryPipeline: YOLO detector + VGG16 + YOLO-Cls ripeness
├── init_db.py            # creates/seeds supermarket_meta.db (36 classes, prices in ₹)
├── config.py             # all paths, thresholds, backend settings (env-overridable)
├── run_pipeline.py       # CLI run of the whole chain (prints per-stage timings)
├── optimize_models.py    # optional: export YOLO models to OpenVINO + benchmark on your PC
├── tests/                # 30 offline tests + 4 real-weight tests on pic.png (skipped without weights)
├── .env.example          # copy to .env and add GROQ_API_KEY
├── .vscode/launch.json   # F5 configs: dashboard, CLI, pytest
├── sample_data/pic.png   # + pic_inventory.json (hand-counted ground truth)
└── (your weights here)   # sku110k_yolo.pt, vgg.h5, freshguard_4class_ripeness_20ep.pt
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python init_db.py                 # optional — without it, the seed table is used offline
cp .env.example .env              # then paste your Groq key into .env
pytest -q                         # 40 passed, 4 skipped without weights; all 44 run once weights are in place
```

## Run

Run every command from the folder that **contains** `streamlit_app.py`.

```bash
streamlit run streamlit_app.py            # or: python streamlit_app.py  (auto-relaunches)
python run_pipeline.py                    # real models on sample_data/pic.png
python run_pipeline.py --sample           # no models: built-in sample inventory
```

Demo safety net: set `FRESHGUARD_SAMPLE_MODE=1` before launching to skip the vision models and use the hand-counted `pic.png` inventory.

## Groq SLM

Get a key at https://console.groq.com/keys and put it in `.env` as `GROQ_API_KEY=...`. The sidebar shows whether the key was found.

Groq writes the descriptive floor instructions, loyalty messages and bundle pitches. Prices, discounts, badges and bundle offers always come from `decision_engine.py`, and any SLM sentence that mentions a price or % the engine did not compute is discarded. With no key, no internet or any Groq error, the template text is used and the dashboard shows a warning, so the demo never crashes. Models (Groq-hosted, non-OpenAI): `qwen/qwen3.8-27b`, then `meta-models/muse-spark-open` if Groq retires the first. Override with `FRESHGUARD_GROQ_MODELS=a,b`.

## Speed

* The 3 models load and warm up in the background as soon as the dashboard opens; the sidebar shows "Models loaded and ready". The first scan no longer waits for TensorFlow/PyTorch start-up.
* The produce and ripeness classifiers run at the same time.
* Scanning the same photo again reuses the earlier result; identical Groq requests are answered from a cache.
* `python run_pipeline.py` prints how long each stage took. `python optimize_models.py` tests whether OpenVINO is faster on your CPU and tells you whether to turn it on.

## Env overrides

`GROQ_API_KEY`, `FRESHGUARD_GROQ_MODELS`, `FRESHGUARD_SAMPLE_MODE`, `FRESHGUARD_PRELOAD` (default 1), `FRESHGUARD_PARALLEL` (default 1), `FRESHGUARD_USE_FAST_MODELS` (default 0), `FRESHGUARD_WEIGHTS_DIR`, `FRESHGUARD_DB_PATH`, `FRESHGUARD_MIN_PRODUCE_CONF` (default 0.35), `FRESHGUARD_CURRENCY` (default ₹), `FRESHGUARD_CURRENCY_CODE` (default INR).
