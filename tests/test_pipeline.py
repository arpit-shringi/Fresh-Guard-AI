# tests/test_pipeline.py — run with:  pytest -q
# Uses FAKE models (no TensorFlow / Ultralytics / weights needed), so it checks the
# wiring, contracts and business math. It does NOT measure model accuracy.
import json
import re
from pathlib import Path

import numpy as np
import pytest

import config
import decision_engine as de
from init_db import initialize_database
from main_engine import ShelfInventoryPipeline, normalize_ripeness_label
from slm_engine import (GroqBackend, SLMEngine, _copy_is_safe, merge_slm_copy, template_recommendations,
                        load_ground_truth)
from tests.conftest import FakeGroqClient

PIC = config.PROJECT_ROOT / "sample_data" / "pic.png"
INV_KEYS = {"Product_Type", "Product_Count", "Ripe_Count", "Unripe_Count", "Overripe_Count", "Rotten_Count"}


# fake models
class _Box:
    def __init__(self, xyxy): self.xyxy = [np.array(xyxy, dtype=float)]

class _DetResult:
    def __init__(self, boxes): self.boxes = boxes

class FakeDetector:
    """10 boxes on a grid + 1 tiny box that must be filtered out."""
    def predict(self, source, **kw):
        h, w = source.shape[:2]
        boxes = [_Box([x, y, x + 200, y + 200]) for x in range(0, 1000, 200) for y in (0, 400)]
        boxes.append(_Box([5, 5, 12, 12]))
        return [_DetResult(boxes)]

class FakeVGG:
    """crop i -> Apple(0) for first 6, Orange(21) next 3, last one low-confidence."""
    def predict(self, batch, batch_size=32, verbose=0):
        out = np.zeros((len(batch), 36), dtype=np.float32)
        for i in range(len(batch)):
            if i < 6:   out[i, 0] = 0.9
            elif i < 9: out[i, 21] = 0.8
            else:       out[i, :] = 1 / 36            # max prob 0.028 -> dropped
        return out

class _Probs:
    def __init__(self, top1): self.top1 = top1

class _ClsResult:
    names = {0: "overripe", 1: "ripe", 2: "rotten", 3: "unripe"}   # Ultralytics sorts alphabetically
    def __init__(self, top1): self.probs = _Probs(top1)

class FakeRipeness:
    names = _ClsResult.names
    def __init__(self): self.calls = []
    def predict(self, source, imgsz=224, verbose=False):
        self.calls.append(len(source))
        seq = [1, 1, 3, 0, 2, 1, 1, 1, 3, 1]  # apples: R R U O Rot R | oranges: R R U | dropped
        start = sum(self.calls[:-1])
        return [_ClsResult(seq[(start + i) % len(seq)]) for i in range(len(source))]


@pytest.fixture
def fake_pipeline():
    return ShelfInventoryPipeline(batch_size=4, detector_model=FakeDetector(),
                                  produce_model=FakeVGG(), ripeness_model=FakeRipeness())


# main_engine
def test_ripeness_label_normalisation():
    assert normalize_ripeness_label("over_ripe") == "Overripe"
    assert normalize_ripeness_label(" Rotten ") == "Rotten"
    assert normalize_ripeness_label("UNRIPE") == "Unripe"
    assert normalize_ripeness_label("fresh") is None


def test_vision_pipeline_contract(fake_pipeline):
    inv = fake_pipeline.process_shelf_image(str(PIC))
    assert set(inv) == {"Apple", "Orange"}
    for row in inv.values():
        assert set(row) == INV_KEYS
        assert row["Product_Count"] == sum(row[k] for k in INV_KEYS - {"Product_Type", "Product_Count"})
    assert inv["Apple"] == {"Product_Type": "Apple", "Product_Count": 6, "Ripe_Count": 3,
                            "Unripe_Count": 1, "Overripe_Count": 1, "Rotten_Count": 1}
    assert inv["Orange"]["Product_Count"] == 3
    stats = fake_pipeline.last_run_stats
    assert stats["detected_boxes"] == 10                     # tiny box filtered
    assert stats["dropped_low_confidence"] == 1
    assert fake_pipeline.ripeness_model.calls == [4, 4, 2]   # manual chunking works


def test_unreadable_image_raises(fake_pipeline, tmp_path):
    bad = tmp_path / "x.png"; bad.write_text("not an image")
    with pytest.raises(ValueError):
        fake_pipeline.process_shelf_image(str(bad))


# decision_engine
def _inv(name, ripe=0, unripe=0, over=0, rot=0):
    return {name: {"Product_Type": name, "Product_Count": ripe + unripe + over + rot,
                   "Ripe_Count": ripe, "Unripe_Count": unripe, "Overripe_Count": over, "Rotten_Count": rot}}


@pytest.mark.parametrize("inv,expected", [
    (_inv("Apple", 10, 6, 5, 3), de.DETERIORATING),
    (_inv("Tomato", 30, 15, 0, 0), de.FRESH_OVERSTOCKED),
    (_inv("Banana", 2, 10, 0, 0), de.UNRIPE_HOLD),
    (_inv("Orange", 10, 2, 1, 0), de.OPTIMAL),
    (_inv("Kiwi", 0, 0, 0, 4), de.ROTTEN_ONLY),
])
def test_decision_scenarios(inv, expected):
    rec = de.DecisionEngine().evaluate_inventory(inv)
    assert next(iter(rec.values()))["scenario"] == expected


def test_empty_bin_is_skipped():
    assert de.DecisionEngine().evaluate_inventory(_inv("Apple")) == {}


def test_markdown_respects_cost_floor_and_max_discount():
    # Banana: ₹7, cost ₹2.50, max 60% -> ₹2.80 (>= cost)
    rec = de.DecisionEngine().evaluate_inventory(_inv("Banana", 1, 0, 5, 0))["Banana"]
    assert rec["new_price"] == 2.80 and rec["discount_pct"] == 60
    # Apple: ₹36 * 0.5 = ₹18 == cost floor
    rec = de.DecisionEngine().evaluate_inventory(_inv("Apple", 1, 0, 5, 0))["Apple"]
    assert rec["new_price"] == 18.0 and rec["new_price"] >= rec["params"]["cost_price"]
    # Grapes: ₹60 * 0.45 = ₹27 < cost ₹29 -> floor wins
    rec = de.DecisionEngine().evaluate_inventory(_inv("Grapes", 1, 0, 5, 0))["Grapes"]
    assert rec["new_price"] == 29.0 and rec["discount_pct"] == 52


def test_string_contract_matches_claude_md():
    actions = de.DecisionEngine().process_inventory_to_slm_actions({**_inv("Apple", 10, 6, 5, 3),
                                                                    **_inv("Tomato", 30, 15, 0, 0)})
    assert all(isinstance(v, str) for v in actions.values())
    assert "50% markdown on Apple (New Price: ₹18, Cost Floor: ₹18)" in actions["Apple"]
    assert actions["Tomato"].startswith("Produce is fresh but overstocked")


def test_single_batched_db_call(tmp_path, monkeypatch):
    db = tmp_path / "meta.db"
    initialize_database(db)
    eng = de.DecisionEngine(db_path=db)          # start-up currency check happens here, not per scan
    calls = []
    import sqlite3
    real_connect = sqlite3.connect
    monkeypatch.setattr(de.sqlite3, "connect", lambda *a, **k: calls.append(a) or real_connect(*a, **k))
    eng.evaluate_inventory({**_inv("Apple", 5), **_inv("Tomato", 5), **_inv("Mango", 5)})
    assert len(calls) == 1 and eng.last_param_source == "sqlite"


def test_missing_db_falls_back_to_seed(tmp_path):
    eng = de.DecisionEngine(db_path=tmp_path / "nope.db")
    rec = eng.evaluate_inventory(_inv("Watermelon", 5))["Watermelon"]
    assert eng.last_param_source == "seed-fallback" and rec["base_price"] == 70.0


#slm_engine
FRONTEND_KEYS = {
    "merchandising_strategies": {"product_type", "status", "strategy"},
    "promotions": {"product_type", "badge", "new_price", "base_price", "loyalty_message"},
    "combos": {"combo_title", "included_products", "bundle_offer", "pitch"},
}


def _assert_frontend_contract(out):
    for key, fields in FRONTEND_KEYS.items():
        assert isinstance(out[key], list)
        for item in out[key]:
            assert fields <= set(item), (key, item)


def test_full_chain_with_fake_vision(fake_pipeline):
    out = SLMEngine(pipeline=fake_pipeline, backend="template").generate_recommendations(str(PIC))
    _assert_frontend_contract(out)
    assert {s["product_type"] for s in out["merchandising_strategies"]} == {"Apple", "Orange"}
    json.dumps(out)  # must be JSON-serialisable for st.json


def test_ground_truth_inventory_matches_contract():
    truth = load_ground_truth()
    assert set(truth) == {"Apple", "Orange"}
    for row in truth.values():
        assert set(row) == INV_KEYS
        assert row["Product_Count"] == sum(row[k] for k in INV_KEYS - {"Product_Type", "Product_Count"})


def test_sample_mode_pic_png_generates_promos_and_bundle():
    out = SLMEngine(use_sample_inventory=True, backend="template").generate_recommendations("")
    _assert_frontend_contract(out)
    sc = {p: d["scenario"] for p, d in out["decisions"].items()}
    assert sc == {"Apple": de.DETERIORATING, "Orange": de.OPTIMAL}   # 3 rotten apples; 12 fresh oranges
    apple = next(p for p in out["promotions"] if p["product_type"] == "Apple")
    assert apple["new_price"] == "₹18" and apple["base_price"] == "₹36"
    assert len(out["promotions"]) == 2 and len(out["combos"]) == 1


def test_every_scenario_renders():
    inv = {**_inv("Apple", 10, 6, 5, 3), **_inv("Tomato", 30, 15), **_inv("Banana", 2, 10),
           **_inv("Orange", 10, 2, 1), **_inv("Kiwi", rot=4)}
    out = template_recommendations(de.DecisionEngine().evaluate_inventory(inv))
    _assert_frontend_contract(out)
    assert len(out["merchandising_strategies"]) == 5
    # every price string shown to customers must be one the decision engine produced
    for p in out["promotions"]:
        assert re.fullmatch(r"₹\d+(\.\d{2})?", p["new_price"])


def test_groq_without_key_falls_back_to_template():
    out = SLMEngine(use_sample_inventory=True, backend="groq").generate_recommendations("")
    _assert_frontend_contract(out)
    assert out["meta"]["generator"] == "template"
    assert "GROQ_API_KEY not set" in out["meta"]["note"]


GROQ_REPLY = json.dumps({"products": {
    "Apple": {"strategy": "Pull the 3 rotten apples now and bag them for disposal. Move soft apples to the "
                          "front quick-sale crate with a bright markdown sign at ₹18. Re-check the bin at 4 pm.",
              "loyalty_message": "Crisp apples are 50% off today at just ₹18 - perfect for a quick apple crumble!",
              "combo_pitch": "Snack on the firm ones, bake with the soft ones - one bag, two treats."},
    "Orange": {"strategy": "Oranges are fresh and at target stock. Keep the display full and facing forward, "
                           "and add a 'Fresh today' card at Rs. 15.",
               "loyalty_message": "Juicy oranges just in at ₹15 - squeeze a fresh glass for breakfast.",
               "combo_pitch": ""}}})


def test_groq_backend_success_path():
    client = FakeGroqClient(GROQ_REPLY)
    eng = SLMEngine(use_sample_inventory=True, backend="groq", llm_backend=GroqBackend(api_key="k", client=client))
    out = eng.generate_recommendations("")
    _assert_frontend_contract(out)
    assert out["meta"]["generator"].startswith("groq:qwen/qwen3.8-27b") and out["meta"]["note"] == ""
    strat = {s["product_type"]: s["strategy"] for s in out["merchandising_strategies"]}
    assert strat["Apple"].startswith("Pull the 3 rotten apples")
    assert out["promotions"][0]["loyalty_message"].startswith("Crisp apples are 50% off")
    assert out["combos"][0]["pitch"].startswith("Snack on the firm ones")
    # prices/badges still come from the decision engine, not the SLM
    assert out["promotions"][0]["badge"] == "50% OFF FLASH SALE" and out["promotions"][0]["new_price"] == "₹18"
    call = client.calls[0]
    assert call["model"] == "qwen/qwen3.8-27b" and call["response_format"] == {"type": "json_object"}
    assert call["reasoning_format"] == "hidden" and call["reasoning_effort"] == "none"
    assert '"selling_price": "₹18"' in call["messages"][1]["content"]   # facts reach the prompt


def test_groq_retries_without_json_mode_on_400():
    class Picky(FakeGroqClient):
        def create(self, **kw):
            if "response_format" in kw:
                raise RuntimeError("Error code: 400 - response_format not supported")
            return super().create(**kw)
    client = Picky("```json\n" + GROQ_REPLY + "\n```")          # fenced reply must still parse
    out = SLMEngine(use_sample_inventory=True, backend="groq",
                    llm_backend=GroqBackend(api_key="k", client=client)).generate_recommendations("")
    assert "fields accepted" in out["meta"]["generator"] and len(client.calls) == 1
    assert "reasoning_format" not in client.calls[0]          # degraded request still JSON mode


def test_groq_network_error_falls_back():
    class Down(FakeGroqClient):
        def create(self, **kw):
            raise ConnectionError("Connection error.")
    out = SLMEngine(use_sample_inventory=True, backend="groq",
                    llm_backend=GroqBackend(api_key="k", client=Down(""))).generate_recommendations("")
    _assert_frontend_contract(out)
    assert out["meta"]["generator"] == "template" and "ConnectionError" in out["meta"]["note"]


def test_slm_copy_guardrail_rejects_invented_numbers():
    rec = de.DecisionEngine().evaluate_inventory(_inv("Apple", 10, 6, 5, 3))
    draft = template_recommendations(rec)
    fake_llm = {"Apple": {"strategy": "Cull the rotten ones and move overripe apples to the front bin.",
                          "loyalty_message": "Apples now 70% off at ₹11 — bake a pie!",   # invented
                          "combo_pitch": "Snack on the firm ones, bake with the soft ones at ₹18."}}
    merged, accepted = merge_slm_copy(draft, fake_llm, rec)
    promo = merged["promotions"][0]["loyalty_message"]
    assert "70%" not in promo and accepted == 2
    a = rec["Apple"]
    assert _copy_is_safe("Now 50% off at ₹18!", a) and _copy_is_safe("Now Rs. 18, was INR 36", a)
    assert not _copy_is_safe("Only Rs 99 today", a)          # invented rupee price
    assert not _copy_is_safe("Just $18 today", a)            # wrong currency
    assert not _copy_is_safe("Was ₹1,200", a)


def test_groq_models_are_groq_hosted_non_openai():
    assert config.SLM_BACKEND == "groq" and config.GROQ_MODELS
    assert not any(m.lower().startswith("openai/") for m in config.GROQ_MODELS)


def test_groq_skips_retired_model_to_next():
    class Retired(FakeGroqClient):
        def create(self, **kw):
            if kw["model"] == "qwen/qwen3.8-27b":
                raise RuntimeError("Error code: 404 - model_decommissioned")
            return super().create(**kw)
    client = Retired(GROQ_REPLY)
    backend = GroqBackend(api_key="k", client=client)
    out = SLMEngine(use_sample_inventory=True, backend="groq", llm_backend=backend).generate_recommendations("")
    assert backend.model == "meta-models/muse-spark-open"
    assert out["meta"]["generator"].startswith("groq:meta-models/muse-spark-open")
    assert client.calls[0]["reasoning_effort"] == "low"


def test_reply_with_think_block_parses():
    client = FakeGroqClient("<think>{draft: maybe}</think>\n" + GROQ_REPLY)
    out = SLMEngine(use_sample_inventory=True, backend="groq",
                    llm_backend=GroqBackend(api_key="k", client=client)).generate_recommendations("")
    assert out["meta"]["note"] == "" and "5 fields accepted" in out["meta"]["generator"]


def test_timings_reported():
    out = SLMEngine(use_sample_inventory=True, backend="groq").generate_recommendations("")
    assert set(out["meta"]["timings_s"]) == {"vision", "decisions", "copy", "total"}


# ------------------------------------------------------------------ rupees + latency (v6)
def test_rupee_database_and_formatting(tmp_path):
    db = tmp_path / "meta.db"
    initialize_database(db)
    import sqlite3
    from init_db import database_currency
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT base_price, cost_price FROM produce_pricing_meta WHERE product_type='Apple'").fetchone() == (36, 18)
        assert c.execute("SELECT COUNT(*) FROM produce_pricing_meta").fetchone()[0] == 36
    assert database_currency(db) == "INR"
    assert config.money(18) == "₹18" and config.money(2.8) == "₹2.80" and config.money(1200) == "₹1,200"


def test_old_dollar_database_is_reseeded(tmp_path):
    import sqlite3
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as c:      # v5-style DB: dollar prices, no db_meta table
        c.execute("CREATE TABLE produce_pricing_meta (product_type TEXT PRIMARY KEY, base_price REAL, cost_price REAL, "
                  "max_discount_pct REAL, target_capacity INT, price_elasticity REAL)")
        c.execute("INSERT INTO produce_pricing_meta VALUES ('Apple', 3.0, 1.5, 0.5, 20, 1.5)")
    eng = de.DecisionEngine(db_path=db)
    rec = eng.evaluate_inventory(_inv("Apple", 5))["Apple"]
    assert eng.last_param_source == "sqlite" and rec["base_price"] == 36.0


def test_classifiers_run_in_parallel():
    import time as _t
    class SlowVGG(FakeVGG):
        def predict(self, *a, **k):
            _t.sleep(0.4); return super().predict(*a, **k)
    class SlowRipe(FakeRipeness):
        def predict(self, *a, **k):
            _t.sleep(0.4); return super().predict(*a, **k)
    pipe = ShelfInventoryPipeline(batch_size=32, detector_model=FakeDetector(),
                                  produce_model=SlowVGG(), ripeness_model=SlowRipe())
    t0 = _t.perf_counter()
    inv = pipe.process_shelf_image(str(PIC))
    took = _t.perf_counter() - t0
    assert inv["Apple"]["Product_Count"] == 6
    assert took < 0.75, f"classifiers ran one after another ({took:.2f}s)"
    assert pipe.last_run_stats["timings_s"]["classify_total"] < 0.75


def test_repeat_scan_uses_cache(fake_pipeline):
    calls = []
    real = fake_pipeline.process_shelf_image
    fake_pipeline.process_shelf_image = lambda p, **k: calls.append(p) or real(p, **k)
    eng = SLMEngine(pipeline=fake_pipeline, backend="groq")
    first = eng.generate_recommendations(str(PIC))
    second = eng.generate_recommendations(str(PIC))
    assert len(calls) == 1 and second["meta"]["vision"]["cached"] is True
    assert first["inventory"] == second["inventory"]


def test_warmup_touches_all_three_models(fake_pipeline):
    took = SLMEngine(pipeline=fake_pipeline, backend="groq").warmup()
    assert took >= 0 and fake_pipeline.ripeness_model.calls == [2]


def test_groq_reply_cache_skips_second_call():
    client = FakeGroqClient(GROQ_REPLY)
    backend = GroqBackend(api_key="k", client=client)
    for _ in range(2):
        SLMEngine(use_sample_inventory=True, backend="groq", llm_backend=backend).generate_recommendations("")
    assert len(client.calls) == 1
