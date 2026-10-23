
import hashlib
import json
import re
import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import config
import decision_engine as de
from main_engine import FRUIT_SET

CUR = config.CURRENCY

def load_ground_truth() -> dict:
    return json.loads(config.GROUND_TRUTH_PATH.read_text(encoding="utf-8"))["inventory"]


SAMPLE_INVENTORY = load_ground_truth()


USE_IDEAS = {
    "Apple": "apple crumble, cinnamon baked apples or a morning smoothie",
    "Banana": "banana bread, pancakes or a protein smoothie",
    "Tomato": "slow-cooked pasta sauce, shakshuka or fresh salsa",
    "Orange": "fresh juice, marmalade or a citrus salad",
    "Mango": "mango lassi, smoothie bowls or salsa",
    "Grapes": "frozen grape snacks, roasted grapes or fruit salad",
    "Pear": "poached pears or a pear-ginger crumble",
    "Kiwi": "smoothie bowls or a tropical fruit salad",
    "Pineapple": "grilled pineapple, fresh juice or pineapple fried rice",
    "Watermelon": "chilled juice, sorbet or a watermelon-feta salad",
    "Pomegranate": "raita, salads or fresh juice",
    "Lemon": "lemonade, marinades or lemon rice",
    "Spinach": "palak paneer, soups or green smoothies",
    "Lettuce": "wraps, salads or a quick stir-fry",
    "Potato": "aloo sabzi, mash or roasted wedges",
    "Capsicum": "stir-fries, stuffed peppers or fajitas",
    "Bell Pepper": "stir-fries, stuffed peppers or fajitas",
    "Cauliflower": "aloo gobi, roasted florets or soup",
    "Carrot": "gajar halwa, soups or roasted carrots",
}
PAIRINGS = {
    "Apple": ["Cinnamon", "Rolled Oats", "Peanut Butter"],
    "Banana": ["Rolled Oats", "Honey", "Yogurt"],
    "Tomato": ["Fresh Mozzarella", "Sweet Basil"],
    "Orange": ["Lemon", "Fresh Mint"],
    "Mango": ["Yogurt", "Cardamom"],
    "Grapes": ["Cheese Platter", "Crackers"],
    "Potato": ["Onion", "Garlic"],
    "Onion": ["Tomato", "Garlic"],
    "Spinach": ["Paneer", "Garlic"],
    "Lettuce": ["Cucumber", "Tomato"],
    "Cucumber": ["Fresh Mint", "Yogurt"],
    "Lemon": ["Ginger", "Honey"],
}


def _uses(prod: str) -> str:
    return USE_IDEAS.get(prod, "smoothies, baking or fresh juice" if prod in FRUIT_SET
                        else "soups, stir-fries or a quick curry")


def _pairs(prod: str) -> List[str]:
    return PAIRINGS.get(prod, ["Yogurt", "Granola"] if prod in FRUIT_SET else ["Onion", "Garlic"])


def _money(x: float) -> str:
    return config.money(x)



STATUS_LABELS = {
    de.ROTTEN_ONLY: "100% Rotten — Cull Immediately",
    de.DETERIORATING: "Deteriorating — Markdown Required",
    de.FRESH_OVERSTOCKED: "Fresh & Overstocked",
    de.UNRIPE_HOLD: "Unripe — Holding Pipeline",
    de.OPTIMAL: "Optimal / Balanced",
}


def template_recommendations(decisions: Dict[str, dict]) -> dict:
    out = {"merchandising_strategies": [], "promotions": [], "combos": []}

    for prod, r in decisions.items():
        c, s = r["counts"], r["scenario"]
        base, new = r["base_price"], r["new_price"]
        pairs = _pairs(prod)

        if s == de.ROTTEN_ONLY:
            strat = (f"URGENT: all {c['rotten']} {prod} units are rotten. Pull the entire bin, discard stock, "
                     f"sanitize the bin and check neighbouring produce for spread before restocking.")
        elif s == de.DETERIORATING:
            cull = (f"Immediately cull {c['rotten']} rotten unit(s) to stop decay spreading. "
                    if c["rotten"] else "")
            strat = (f"{cull}Move the {c['overripe']} overripe unit(s) to a front quick-sale bin at "
                     f"{_money(new)}, keep firm stock separate, and route anything unsold by close "
                     f"to the bakery/juice counter.")
        elif s == de.FRESH_OVERSTOCKED:
            excess = c["sellable"] - r["params"]["target_capacity"]
            strat = (f"Stock is {excess} unit(s) over the target of {r['params']['target_capacity']}. "
                     f"Move the excess to a high-traffic front-of-store endcap next to "
                     f"{' and '.join(pairs)} to drive full-price volume; no markdown needed.")
        elif s == de.UNRIPE_HOLD:
            rotate = max(0, c["unripe"] // 2)
            strat = (f"{c['unripe']} of {c['sellable']} units are unripe. Rotate about {rotate} unit(s) into "
                     f"cold storage to slow ripening and build 'Eat Now, Ripen Later' mixed packs from the rest.")
        else:
            strat = (f"Stock and ripeness are balanced ({c['sellable']} sellable). Keep standard placement "
                     f"and pricing at {_money(base)}; re-scan at the next shift change.")
        out["merchandising_strategies"].append(
            {"product_type": prod, "status": STATUS_LABELS[s], "strategy": strat})

        if s == de.DETERIORATING:
            out["promotions"].append({
                "product_type": prod, "badge": f"{r['discount_pct']}% OFF FLASH SALE",
                "new_price": _money(new), "base_price": _money(base),
                "loyalty_message": (f"Sweet, fully ripe {prod} now just {_money(new)} today only. "
                                    f"Perfect for {_uses(prod)}."),
            })
        elif s == de.FRESH_OVERSTOCKED:
            out["promotions"].append({
                "product_type": prod, "badge": "FRESH PICK • BUNDLE DEAL",
                "new_price": _money(base), "base_price": _money(base),
                "loyalty_message": (f"Peak-fresh {prod} just landed. Grab some with {pairs[0]} for "
                                    f"{_uses(prod)}."),
            })
        elif s == de.OPTIMAL:
            out["promotions"].append({
                "product_type": prod, "badge": "FARM FRESH TODAY",
                "new_price": _money(base), "base_price": _money(base),
                "loyalty_message": f"Today's {prod} is farm-fresh and in perfect condition — ideal for {_uses(prod)}.",
            })

        if s == de.FRESH_OVERSTOCKED:
            out["combos"].append({
                "combo_title": f"{prod} + {pairs[0]} Kit",
                "included_products": [prod] + pairs,
                "bundle_offer": f"Buy {prod} at full price, get 10% off {pairs[0]}",
                "pitch": f"Everything you need for {_uses(prod).split(',')[0]} in one grab.",
                "anchor_product": prod,
            })
        elif s == de.UNRIPE_HOLD:
            out["combos"].append({
                "combo_title": f"{prod} 'Eat Now, Ripen Later' Pack",
                "included_products": [f"{prod} (Ripe)", f"{prod} (Unripe)"],
                "bundle_offer": f"Mixed-ripeness pack at the regular {_money(base)} per unit",
                "pitch": "Some for today, some ripening on your counter for later in the week.",
                "anchor_product": prod,
            })
        elif s == de.DETERIORATING and c["sellable"] - c["overripe"] > 0:
            out["combos"].append({
                "combo_title": f"{prod} 'Eat Now & Bake Later' Value Bag",
                "included_products": [f"{prod} (Firm + Very Ripe Mix)"],
                "bundle_offer": f"Mixed bag at the {r['discount_pct']}% markdown price ({_money(new)} per unit)",
                "pitch": f"Firm ones for snacking, very ripe ones for {_uses(prod).split(',')[0]}.",
                "anchor_product": prod,
            })
    return out


_PCT_CLAIM = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_MONEY_CLAIM = re.compile(r"(₹|\bRs\.?|\bINR|\$|€|£)\s?(\d[\d,]*(?:\.\d{1,2})?)", re.IGNORECASE)
_RUPEE_SYMBOLS = {"₹", "rs", "rs.", "inr"}


def _copy_is_safe(text: str, record: dict) -> bool:

    allowed_pct = {float(record["discount_pct"]), 10.0}            # 10% = fixed pairing offer
    allowed_money = {round(record["base_price"], 2), round(record["new_price"], 2)}
    for pct in _PCT_CLAIM.findall(text):
        if float(pct) not in allowed_pct:
            return False
    rupees = config.CURRENCY_CODE == "INR"
    for symbol, amount in _MONEY_CLAIM.findall(text):
        sym = symbol.lower()
        right_currency = sym in _RUPEE_SYMBOLS if rupees else symbol == config.CURRENCY
        if not right_currency or round(float(amount.replace(",", "")), 2) not in allowed_money:
            return False
    return True


FIELD_LIMITS = {"strategy": 700, "loyalty_message": 400, "combo_pitch": 300}


def _extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def _reasoning_kwargs(model: str) -> dict:
    m = model.lower()
    if "qwen" in m:
        return {"reasoning_format": "hidden", "reasoning_effort": "none"}
    if "muse-spark" in m:                     
        return {"reasoning_format": "hidden", "reasoning_effort": "low"}
    return {}


def _is_bad_request(e: Exception) -> bool:
    return "400" in str(e) or "BadRequest" in type(e).__name__


def _is_model_unavailable(e: Exception) -> bool:
    s = str(e).lower()
    return ("404" in s or "notfound" in type(e).__name__.lower() or "model_not_found" in s
            or "decommissioned" in s or "does not exist" in s)


class GroqBackend:


    SYSTEM = ("You are FreshGuard, an expert merchandising assistant for an Indian supermarket's fresh-produce "
              "section. You write clear, practical, specific copy in Indian English. Reply with ONE JSON object "
              "only. Prices are in Indian rupees: always write them with the ₹ symbol exactly as given. Never "
              "state any price, discount or percentage except the exact values given in FACTS.")

    def __init__(self, api_key: Optional[str] = None, models: Optional[List[str]] = None,
                 timeout: float = config.GROQ_TIMEOUT_S, client=None):
        self.api_key = config.GROQ_API_KEY if api_key is None else api_key
        self.models = list(models or config.GROQ_MODELS)
        self.model = self.models[0]             
        self.timeout, self._client = timeout, client
        self._cache: "OrderedDict[str, Tuple[str, dict]]" = OrderedDict() 

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("GROQ_API_KEY not set (copy .env.example to .env and add your key)")
            try:
                from groq import Groq
            except ImportError as e:
                raise RuntimeError("groq package not installed (pip install groq)") from e
            self._client = Groq(api_key=self.api_key, timeout=self.timeout, max_retries=1)
        return self._client

    @staticmethod
    def build_facts(decisions: Dict[str, dict], draft: dict) -> Dict[str, dict]:
        combos = {c.get("anchor_product"): c for c in draft.get("combos", [])}
        status = {m["product_type"]: m["status"] for m in draft.get("merchandising_strategies", [])}
        facts = {}
        for p, r in decisions.items():
            combo = combos.get(p)
            facts[p] = {
                "status": status.get(p, r["scenario"]),
                "directive": de.DecisionEngine.directive_for(r),
                "stock_counts": r["counts"],
                "shelf_target_units": r["params"]["target_capacity"],
                "selling_price": _money(r["new_price"]),
                "regular_price": _money(r["base_price"]),
                "discount_percent": r["discount_pct"],
                "bundle": ({"title": combo["combo_title"], "offer": combo["bundle_offer"],
                            "items": combo["included_products"]} if combo else None),
            }
        return facts

    def build_messages(self, decisions: Dict[str, dict], draft: dict) -> list:
        user = ("For EACH product in FACTS, follow its directive and write:\n"
                '- "strategy": a descriptive 3-4 sentence instruction for the store manager and floor '
                "staff: what to pull or cull, where to move stock, what signage to put up, and when.\n"
                '- "loyalty_message": 1-2 warm sentences for the customer loyalty app with one '
                "concrete recipe or use idea.\n"
                '- "combo_pitch": one catchy sentence selling the bundle, or "" if bundle is null.\n'
                "Use the exact product names as keys. Return JSON shaped like "
                '{"products": {"<product>": {"strategy": "...", "loyalty_message": "...", "combo_pitch": "..."}}}\n\n'
                "FACTS:\n" + json.dumps(self.build_facts(decisions, draft), indent=1, ensure_ascii=False))
        return [{"role": "system", "content": self.SYSTEM}, {"role": "user", "content": user}]

    def _ask(self, client, model: str, base: dict):
        extras = _reasoning_kwargs(model)
        attempts = [{**extras, "response_format": {"type": "json_object"}},
                    {"response_format": {"type": "json_object"}},
                    {}]
        for i, extra in enumerate(attempts):
            try:
                return client.chat.completions.create(model=model, **base, **extra)
            except Exception as e:
                if not _is_bad_request(e) or i == len(attempts) - 1:
                    raise

    def rewrite(self, decisions: Dict[str, dict], draft: dict) -> Dict[str, dict]:
        messages = self.build_messages(decisions, draft)
        key = hashlib.sha1(json.dumps(messages, sort_keys=True).encode("utf-8")).hexdigest()
        if key in self._cache:                    
            self.model, products = self._cache[key]
            self._cache.move_to_end(key)
            return json.loads(json.dumps(products))
        client = self._get_client()
        base = dict(messages=messages, temperature=0.6, max_completion_tokens=1500)
        last_error = None
        for model in self.models:              
            try:
                resp = self._ask(client, model, base)
            except Exception as e:
                if _is_model_unavailable(e):
                    last_error = e
                    continue
                raise
            self.model = model
            products = _extract_json(resp.choices[0].message.content).get("products", {})
            products = products if isinstance(products, dict) else {}
            self._cache[key] = (model, products)
            while len(self._cache) > 64:
                self._cache.popitem(last=False)
            return json.loads(json.dumps(products))
        raise RuntimeError(f"No Groq model available from {self.models}: {last_error}")


def merge_slm_copy(draft: dict, slm_products: Dict[str, dict], decisions: Dict[str, dict]) -> Tuple[dict, int]:
    accepted = 0

    def ok(prod, field) -> Optional[str]:
        val = (slm_products.get(prod) or {}).get(field)
        limit = FIELD_LIMITS.get(field, 400)
        if isinstance(val, str) and 10 <= len(val.strip()) <= limit and _copy_is_safe(val, decisions[prod]):
            return val.strip()
        return None

    for item in draft["merchandising_strategies"]:
        if (v := ok(item["product_type"], "strategy")):
            item["strategy"], accepted = v, accepted + 1
    for item in draft["promotions"]:
        if (v := ok(item["product_type"], "loyalty_message")):
            item["loyalty_message"], accepted = v, accepted + 1
    for item in draft["combos"]:
        if (v := ok(item.get("anchor_product", ""), "combo_pitch")):
            item["pitch"], accepted = v, accepted + 1
    return draft, accepted



class SLMEngine:
    def __init__(self, use_sample_inventory: bool = False, backend: str = config.SLM_BACKEND,
                 pipeline=None, decision_engine=None, llm_backend=None):
        self.use_sample_inventory = use_sample_inventory
        self.backend_name = backend
        self._pipeline = pipeline                       
        self.decision_engine = decision_engine or de.DecisionEngine()
        self.llm = llm_backend or (GroqBackend() if backend == "groq" else None)
        self._lock = threading.Lock()             
        self._scan_cache: "OrderedDict[str, Tuple[dict, dict]]" = OrderedDict()

    @property
    def pipeline(self):
        if self._pipeline is None:
            from main_engine import ShelfInventoryPipeline
            self._pipeline = ShelfInventoryPipeline()
        return self._pipeline

    def _scan(self, image_path: str) -> Tuple[dict, dict]:
        with open(image_path, "rb") as f:
            key = hashlib.sha1(f.read()).hexdigest()
        with self._lock:
            if key in self._scan_cache:
                inv, stats = self._scan_cache[key]
                self._scan_cache.move_to_end(key)
                return json.loads(json.dumps(inv)), {**stats, "cached": True}
            inv = self.pipeline.process_shelf_image(image_path)
            stats = {"mode": "vision models", **getattr(self.pipeline, "last_run_stats", {})}
            self._scan_cache[key] = (json.loads(json.dumps(inv)), stats)
            while len(self._scan_cache) > config.SCAN_CACHE_SIZE:
                self._scan_cache.popitem(last=False)
            return inv, stats

    def warmup(self) -> float:
        return 0.0 if self.use_sample_inventory else self.pipeline.warmup()

    def generate_recommendations(self, image_path: str) -> dict:
        t0 = time.perf_counter()
        if self.use_sample_inventory:
            inventory, vision_stats = json.loads(json.dumps(SAMPLE_INVENTORY)), {"mode": "sample inventory"}
        else:
            inventory, vision_stats = self._scan(image_path)

        t1 = time.perf_counter()
        decisions = self.decision_engine.evaluate_inventory(inventory)
        t2 = time.perf_counter()

        result = template_recommendations(decisions)
        generator, note = "template", ""
        if self.llm is not None and decisions:
            try:
                result, n = merge_slm_copy(result, self.llm.rewrite(decisions, result), decisions)
                model = getattr(self.llm, "model", self.backend_name)
                generator = f"{self.backend_name}:{model} ({n} fields accepted)"
            except Exception as e:                    
                note = f"SLM unavailable ({type(e).__name__}: {e}); used template fallback."

        t3 = time.perf_counter()
        result["inventory"] = inventory
        result["decisions"] = {
            p: {"scenario": r["scenario"], "ripeness_index": r["ripeness_index"],
                "is_overstocked": r["is_overstocked"], "discount_pct": r["discount_pct"],
                "new_price": r["new_price"], "base_price": r["base_price"],
                "directive": de.DecisionEngine.directive_for(r)}
            for p, r in decisions.items()
        }
        result["meta"] = {"generator": generator, "note": note, "vision": vision_stats,
                          "pricing_params": self.decision_engine.last_param_source,
                          "timings_s": {"vision": round(t1 - t0, 3), "decisions": round(t2 - t1, 3),
                                        "copy": round(t3 - t2, 3), "total": round(t3 - t0, 3)}}
        return result


if __name__ == "__main__":
    print(json.dumps(SLMEngine(use_sample_inventory=True).generate_recommendations(""), indent=2))
