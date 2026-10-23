# tests/test_real_weights.py — REAL models on sample_data/pic.png
# Runs only when all three weight files are in the project folder and TensorFlow +
# Ultralytics are installed (i.e. on your machine); skipped everywhere else.
#   sku110k_yolo.pt | vgg.h5 | freshguard_4class_ripeness_20ep.pt
import json

import pytest

import config
from main_engine import PRODUCE_CLASSES_36, weight_file_report

WEIGHTS = (config.DETECTOR_WEIGHTS, config.PRODUCE_WEIGHTS, config.RIPENESS_WEIGHTS)
pytestmark = pytest.mark.skipif(not all(p.exists() for p in WEIGHTS),
                                reason="real weights not in project folder:\n" + weight_file_report())
PIC = config.PROJECT_ROOT / "sample_data" / "pic.png"
INV_KEYS = {"Product_Type", "Product_Count", "Ripe_Count", "Unripe_Count", "Overripe_Count", "Rotten_Count"}


@pytest.fixture(scope="module")
def real_pipeline():
    pytest.importorskip("tensorflow")
    pytest.importorskip("ultralytics")
    from main_engine import ShelfInventoryPipeline
    return ShelfInventoryPipeline()


def test_ripeness_model_has_the_4_expected_classes(real_pipeline):
    from main_engine import normalize_ripeness_label
    names = real_pipeline.ripeness_model.names
    mapped = {normalize_ripeness_label(n) for n in names.values()}
    assert mapped == {"Ripe", "Unripe", "Overripe", "Rotten"}, f"unexpected ripeness classes: {names}"


def test_vgg_outputs_36_classes(real_pipeline):
    assert real_pipeline.produce_model.output_shape[-1] == len(PRODUCE_CLASSES_36)


def test_real_inventory_on_pic_png(real_pipeline):
    inv = real_pipeline.process_shelf_image(str(PIC))
    stats = real_pipeline.last_run_stats
    truth = json.loads(config.GROUND_TRUTH_PATH.read_text(encoding="utf-8"))["inventory"]
    print("\nREAL INVENTORY:", json.dumps(inv, indent=1), "\nSTATS:", stats)
    print("GROUND TRUTH:", {p: r["Product_Count"] for p, r in truth.items()})
    assert stats["detected_boxes"] > 0, "detector found nothing in pic.png"
    assert inv, f"every crop was dropped (stats={stats}); try FRESHGUARD_MIN_PRODUCE_CONF=0.2"
    for prod, row in inv.items():
        assert prod in PRODUCE_CLASSES_36.values() and set(row) == INV_KEYS
    assert stats["unknown_ripeness_labels"] == 0


def test_real_chain_generates_promos_or_bundles(real_pipeline):
    from slm_engine import SLMEngine
    out = SLMEngine(pipeline=real_pipeline, backend="template").generate_recommendations(str(PIC))
    assert out["merchandising_strategies"]
    assert out["promotions"] or out["combos"], f"no promos/bundles for inventory {out['inventory']}"
