import json
from pathlib import Path
from slm_engine.schemas import ItemInput, SLMGeneratedContent

def generate_promo_and_recipe(item: ItemInput) -> dict:
    if item.recommended_action == "DISCARD":
        return {
            "headline": f"QUALITY ALERT: {item.name} removed from shelf due to quality standards.",
            "recipe_title": "N/A - Item Unsafe for Consumption",
            "prep_time_mins": 0,
            "ingredients": [],
            "instructions": ["Item flagged for bio-waste processing / composting."],
            "waste_prevented_kg": 0.0
        }

    elif item.recommended_action == "BUNDLE":
        mock_response = {
            "headline": f"Fresh Stock Deal: Create the Ultimate Dish with {item.name}s!",
            "recipe_title": f"Fresh {item.name} Salad & Dip Combo",
            "prep_time_mins": 8,
            "ingredients": [f"Fresh {item.name}s", "Olive Oil", "Fresh Herbs", "Feta Cheese"],
            "instructions": [f"Dice the fresh {item.name}s.", "Toss with olive oil and crumbled feta.", "Serve as a fresh side dish."],
            "waste_prevented_kg": round(item.stock_count * 0.12, 2)
        }

    else:
        mock_response = {
            "headline": f"Flash Clearance: Save Big on {item.name}s Today Only!",
            "recipe_title": f"10-Minute Zero-Waste {item.name} Spread",
            "prep_time_mins": 10,
            "ingredients": [f"2 Ripe {item.name}s", "1 Lemon", "Salt & Black Pepper"],
            "instructions": [f"Mash or chop the ripe {item.name}s.", "Mix with lemon juice and seasoning.", "Enjoy with warm toast or crackers."],
            "waste_prevented_kg": round(item.stock_count * 0.15, 2)
        }

    validated = SLMGeneratedContent(**mock_response)
    return validated.model_dump()


if __name__ == "__main__":
    mock_file_path = Path(__file__).parent.parent / "mock_data.json"
    
    if not mock_file_path.exists():
        print(f"Error: Could not find {mock_file_path}")
    else:
        with open(mock_file_path, "r") as f:
            inventory = json.load(f)
        
        print(f"=== TESTING SLM GENERATOR ON {len(inventory)} MOCK ITEMS ===")
        for raw_item in inventory:
            item_obj = ItemInput(**raw_item)
            slm_result = generate_promo_and_recipe(item_obj)
            
            raw_item["slm_generated"] = slm_result
            
            print(f"\nItem: {item_obj.name} | Action: {item_obj.recommended_action}")
            print(f"Headline: {slm_result['headline']}")
            print(f"Recipe:   {slm_result['recipe_title']}")
            print(f"Prep Time: {slm_result['prep_time_mins']} mins | Waste Prevented: {slm_result['waste_prevented_kg']} kg")

        print("\n✓ SLM Engine validation complete! Ready for FastAPI integration.")