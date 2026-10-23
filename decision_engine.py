# decision_engine.py: RETAIL DECISION MATRIX & SLM DIRECTIVE ROUTER
# Two public methods:
#   evaluate_inventory(inventory)              -> Dict[str, dict]  (structured; used by slm_engine)
#   process_inventory_to_slm_actions(inventory) -> Dict[str, str]  (original contract, CLAUDE.md §3C)
#
# Changes vs. previous version:
#   * ONE batched SQLite query per scan (`WHERE product_type IN (...)`), no per-product SELECT.
#   * Offline fallback = the same seed table init_db.py writes (no separate mock_db to drift).
#   * Structured output, so slm_engine never has to regex prices back out of prose.
#   * Scenario A directive also tells staff how many rotten units to cull.
import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable

import config
from init_db import PRODUCE_SEED_DATA, database_currency, initialize_database

PARAM_KEYS = ("base_price", "cost_price", "max_discount_pct", "target_capacity", "price_elasticity")

SEED_PARAMS = {row[0]: dict(zip(PARAM_KEYS, row[1:])) for row in PRODUCE_SEED_DATA}
DEFAULT_PARAMS = {"base_price": 2.00, "cost_price": 1.00, "max_discount_pct": 0.30,
                  "target_capacity": 25, "price_elasticity": 1.0}

# Scenario identifiers (stable strings — slm_engine and the UI key off these)
ROTTEN_ONLY = "ROTTEN_ONLY"
DETERIORATING = "A_DETERIORATING"
FRESH_OVERSTOCKED = "B_FRESH_OVERSTOCKED"
UNRIPE_HOLD = "C_UNRIPE_HOLD"
OPTIMAL = "D_OPTIMAL"


class DecisionEngine:
    def __init__(self, db_path: Path = config.DB_PATH):
        self.db_path = Path(db_path)
        self.overripe_alert_pct = config.OVERRIPE_ALERT_PCT
        self.ripe_peak_pct = config.RIPE_PEAK_PCT
        self.unripe_hold_pct = config.UNRIPE_HOLD_PCT
        self.last_param_source = "none"   # "sqlite" | "seed-fallback" — shown in the UI
        # One-time check at start-up (not per scan): an old dollar database is
        # reseeded with the rupee prices so the UI can never show "₹3" apples.
        if self.db_path.exists() and database_currency(self.db_path) != config.CURRENCY_CODE:
            print(f"  -> {self.db_path.name} is not in {config.CURRENCY_CODE}; reseeding with rupee prices.")
            try:
                initialize_database(self.db_path)
            except Exception as e:      # read-only file etc.: the seed fallback still has rupee prices
                print(f"  -> Reseed failed ({e}); using built-in rupee prices.")
                self.db_path = Path(str(self.db_path) + ".unavailable")

    # DATABASE: single batched call per scan, deterministic offline fallback
    def fetch_all_db_parameters_once(self, product_types: Iterable[str]) -> Dict[str, dict]:
        product_types = list(dict.fromkeys(product_types))  # de-dupe, keep order
        if not product_types:
            return {}

        db_rows: Dict[str, dict] = {}
        if self.db_path.exists():
            placeholders = ",".join(["?"] * len(product_types))
            query = (f"SELECT product_type, base_price, cost_price, max_discount_pct, "
                     f"target_capacity, price_elasticity "
                     f"FROM produce_pricing_meta WHERE product_type IN ({placeholders})")
            try:
                with sqlite3.connect(self.db_path) as conn:
                    rows = conn.execute(query, tuple(product_types)).fetchall()
                db_rows = {
                    r[0]: {"base_price": float(r[1]), "cost_price": float(r[2]),
                           "max_discount_pct": float(r[3]), "target_capacity": int(r[4]),
                           "price_elasticity": float(r[5])}
                    for r in rows
                }
                self.last_param_source = "sqlite"
            except sqlite3.Error as e:
                print(f"  -> DB query failed ({e}); using seed fallback.")
                self.last_param_source = "seed-fallback"
        else:
            self.last_param_source = "seed-fallback"

        return {
            p: {"product_type": p, **(db_rows.get(p) or SEED_PARAMS.get(p) or DEFAULT_PARAMS)}
            for p in product_types
        }

    # CORE MATRIX
    def evaluate_inventory(self, inventory_dict: Dict[str, dict]) -> Dict[str, dict]:
        """Returns {product_type: decision_record} with all numbers the SLM layer needs."""
        all_params = self.fetch_all_db_parameters_once(inventory_dict.keys())
        decisions: Dict[str, dict] = {}

        for prod_type, stats in inventory_dict.items():
            p = all_params[prod_type]
            ripe = int(stats.get("Ripe_Count", 0))
            unripe = int(stats.get("Unripe_Count", 0))
            overripe = int(stats.get("Overripe_Count", 0))
            rotten = int(stats.get("Rotten_Count", 0))
            sellable = ripe + unripe + overripe

            record = {
                "product_type": prod_type,
                "counts": {"total": int(stats.get("Product_Count", sellable + rotten)), "ripe": ripe,
                           "unripe": unripe, "overripe": overripe, "rotten": rotten, "sellable": sellable},
                "params": p,
                "base_price": round(float(p["base_price"]), 2),
                "new_price": round(float(p["base_price"]), 2),
                "discount_pct": 0,
            }

            # Edge case: empty or 100% rotten bin
            if sellable == 0:
                if rotten > 0:
                    record.update(scenario=ROTTEN_ONLY, ripeness_index=None, is_overstocked=False,
                                  pct={"ripe": 0.0, "unripe": 0.0, "overripe": 0.0})
                    decisions[prod_type] = record
                continue

            ri = (0.0 * unripe + 0.5 * ripe + 1.0 * overripe) / sellable
            pct = {"ripe": ripe / sellable * 100, "unripe": unripe / sellable * 100,
                   "overripe": overripe / sellable * 100}
            is_overstocked = sellable > p["target_capacity"]

            if pct["overripe"] >= self.overripe_alert_pct or ri >= config.RI_DETERIORATING or rotten > 0:
                scenario = DETERIORATING
                new_price = round(p["base_price"] * (1 - p["max_discount_pct"]), 2)
                new_price = max(new_price, round(float(p["cost_price"]), 2))   # cost floor
                record["new_price"] = new_price
                record["discount_pct"] = int(round((1 - new_price / p["base_price"]) * 100))
            elif is_overstocked and (pct["ripe"] >= self.ripe_peak_pct or config.RI_UNRIPE <= ri < config.RI_DETERIORATING):
                scenario = FRESH_OVERSTOCKED
            elif pct["unripe"] >= self.unripe_hold_pct or ri < config.RI_UNRIPE:
                scenario = UNRIPE_HOLD
            else:
                scenario = OPTIMAL

            record.update(scenario=scenario, ripeness_index=round(ri, 3),
                          is_overstocked=is_overstocked, pct={k: round(v, 1) for k, v in pct.items()})
            decisions[prod_type] = record

        return decisions

    # DIRECTIVES (original Dict[str, str] contract)
    @staticmethod
    def directive_for(record: dict) -> str:
        c, prod, money = record["counts"], record["product_type"], config.money
        s = record["scenario"]
        if s == ROTTEN_ONLY:
            return (f"Produce is 100% rotten. Generate an urgent internal operations alert to cull all "
                    f"{c['rotten']} {prod} units and sanitize the bin.")
        if s == DETERIORATING:
            cull = f" Cull {c['rotten']} rotten units first." if c["rotten"] else ""
            return (f"Produce is deteriorating.{cull} Generate a targeted loyalty app promotion offering a "
                    f"{record['discount_pct']}% markdown on {prod} (New Price: {money(record['new_price'])}, "
                    f"Cost Floor: {money(record['params']['cost_price'])}). Include a creative recipe or "
                    f"product-use suggestion (e.g., baking, smoothies, sauces) to encourage immediate customer consumption.")
        if s == FRESH_OVERSTOCKED:
            return (f"Produce is fresh but overstocked. Generate a cross-merchandising strategy and "
                    f"loyalty app bundle to drive full-price sales of {prod}. Suggest a complementary "
                    f"product pairing and recommend optimal store placement (e.g., front-of-store endcap).")
        if s == UNRIPE_HOLD:
            return (f"Produce is highly unripe. Generate a merchandising strategy for 'Eat Now, Ripen Later' "
                    f"mixed packs of {prod}, and suggest to the store manager what portion to rotate "
                    f"into cold storage to pause ripening.")
        return (f"Produce is at peak freshness and optimal stock. Generate a short, engaging push "
                f"notification for the loyalty app highlighting the farm-fresh quality of today's "
                f"{prod} at standard pricing ({money(record['base_price'])}).")

    def process_inventory_to_slm_actions(self, inventory_dict: Dict[str, dict]) -> Dict[str, str]:
        return {p: self.directive_for(r) for p, r in self.evaluate_inventory(inventory_dict).items()}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # ₹ on Windows consoles
    mock_main_engine_output = {
        "Apple": {"Product_Type": "Apple", "Product_Count": 24, "Ripe_Count": 10,
                  "Unripe_Count": 6, "Overripe_Count": 5, "Rotten_Count": 3},
        "Tomato": {"Product_Type": "Tomato", "Product_Count": 45, "Ripe_Count": 30,
                   "Unripe_Count": 15, "Overripe_Count": 0, "Rotten_Count": 0},
    }
    engine = DecisionEngine()
    print("FINAL SLM ACTION DICTIONARY:")
    print(json.dumps(engine.process_inventory_to_slm_actions(mock_main_engine_output), indent=4, ensure_ascii=False))
    print(f"(parameters from: {engine.last_param_source})")
