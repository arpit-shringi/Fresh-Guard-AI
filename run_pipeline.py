# run_pipeline.py: COMMAND-LINE RUN OF THE FULL CHAIN (replaces test_main_engine.py)
#   python run_pipeline.py                         # sample_data/pic.png, real models
#   python run_pipeline.py path/to/shelf.jpg
#   python run_pipeline.py --sample                # skip vision models
import argparse
import json
import sys
from pathlib import Path

import config
from slm_engine import SLMEngine


def main():
    # Windows terminals (Git Bash, cmd with a non-UTF-8 code page) default to cp1252 and
    # crash on emoji / em-dashes. Force UTF-8 and never crash on a stray character.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="FreshGuard AI end-to-end run")
    ap.add_argument("image", nargs="?", default=str(config.PROJECT_ROOT / "sample_data" / "pic.png"))
    ap.add_argument("--sample", action="store_true", help="use the built-in sample inventory")
    args = ap.parse_args()

    out = SLMEngine(use_sample_inventory=args.sample, backend="groq").generate_recommendations(args.image)

    print("\n" + "=" * 64 + "\n 🛒 FRESHGUARD AI — SHELF REPORT\n" + "=" * 64)
    for prod, d in out["decisions"].items():
        inv = out["inventory"][prod]
        print(f"\n{prod.upper()}  total={inv['Product_Count']}  ripe={inv['Ripe_Count']}  "
              f"unripe={inv['Unripe_Count']}  overripe={inv['Overripe_Count']}  rotten={inv['Rotten_Count']}")
        print(f"  scenario={d['scenario']}  RI={d['ripeness_index']}  overstocked={d['is_overstocked']}  "
              f"price={config.CURRENCY}{d['new_price']:.2f} (base {config.CURRENCY}{d['base_price']:.2f})")
        print(f"  directive: {d['directive']}")
    # Real models vs the hand-counted inventory of pic.png
    if not args.sample and Path(args.image).name == "pic.png" and config.GROUND_TRUTH_PATH.exists():
        truth = json.loads(config.GROUND_TRUTH_PATH.read_text(encoding="utf-8"))["inventory"]
        print("\nGROUND TRUTH vs DETECTED (pic.png)   [truth/detected]")
        for prod in sorted(set(truth) | set(out["inventory"])):
            t, d = truth.get(prod, {}), out["inventory"].get(prod, {})
            cells = [f"{k.split('_')[0]} {t.get(k, 0)}/{d.get(k, 0)}" for k in
                     ("Product_Count", "Ripe_Count", "Unripe_Count", "Overripe_Count", "Rotten_Count")]
            print(f"  {prod:<12} " + " | ".join(cells))
    print("\nMETA:", json.dumps(out["meta"]))
    print("TIMINGS (s):", out["meta"]["timings_s"], "| vision stages:", out["meta"]["vision"].get("timings_s"))
    print("\nFULL PAYLOAD:\n" + json.dumps({k: out[k] for k in ("merchandising_strategies", "promotions", "combos")},
                                           indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
