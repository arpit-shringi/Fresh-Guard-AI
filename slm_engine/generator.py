import os
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from slm_engine.schemas import ItemInput, SLMGeneratedContent

load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None


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

    if not client:
        print("[Warning] GROQ_API_KEY not found in .env. Using fallback generation.")
        return {
            "headline": f"Special Offer on {item.name}s!",
            "recipe_title": f"Quick {item.name} Recipe",
            "prep_time_mins": 10,
            "ingredients": [f"{item.name}", "Basic seasonings"],
            "instructions": ["Prepare and enjoy immediately."],
            "waste_prevented_kg": round(item.stock_count * 0.15, 2)
        }

    system_prompt = """You are FreshGuard SLM, an AI specialized in sustainable retail merchandising.
Your task is to generate promotional headlines and zero-waste recipes for expiring or overstocked store items.

STRICT CONSTRAINTS:
1. NEVER alter, calculate, or invent prices.
2. Return ONLY a valid JSON object matching the requested schema.
3. Keep recipes practical (3-5 basic household ingredients, under 15 mins prep time).
"""

    user_prompt = f"""
Item Name: {item.name}
Recommended Strategy: {item.recommended_action}
Freshness Stage: {item.freshness_stage}
Stock Count: {item.stock_count} units
Original Price: ₹{item.original_price}
Approved Sale Price: ₹{item.recommended_price}

Task:
Generate a catchy promotional headline and a zero-waste recipe using {item.name}.

Required JSON Schema:
{{
  "headline": "catchy promo headline string",
  "recipe_title": "recipe name string",
  "prep_time_mins": integer_number,
  "ingredients": ["ingredient 1", "ingredient 2"],
  "instructions": ["step 1", "step 2"],
  "waste_prevented_kg": float_number
}}
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=500
        )

        raw_text = response.choices[0].message.content
        parsed_json = json.loads(raw_text)

        if "waste_prevented_kg" not in parsed_json or not isinstance(parsed_json["waste_prevented_kg"], (int, float)):
            parsed_json["waste_prevented_kg"] = round(item.stock_count * 0.15, 2)

        validated = SLMGeneratedContent(**parsed_json)
        return validated.model_dump()

    except Exception as e:
        print(f"[SLM Engine Error] API generation failed: {e}")
        return {
            "headline": f"Flash Clearance: Save on {item.name}!",
            "recipe_title": f"10-Minute {item.name} Express Meal",
            "prep_time_mins": 10,
            "ingredients": [f"{item.name}", "Olive Oil", "Salt & Pepper"],
            "instructions": ["Slice produce and toss with oil and spices.", "Serve immediately."],
            "waste_prevented_kg": round(item.stock_count * 0.15, 2)
        }


if __name__ == "__main__":
    mock_file_path = Path(__file__).parent.parent / "mock_data.json"
    
    if not mock_file_path.exists():
        print(f"Error: Could not find {mock_file_path}")
    else:
        with open(mock_file_path, "r") as f:
            inventory = json.load(f)
        
        for raw_item in inventory:
            item_obj = ItemInput(**raw_item)
            slm_result = generate_promo_and_recipe(item_obj)
            
            print(f"\nItem: {item_obj.name} | Action: {item_obj.recommended_action}")
            print(f"Headline: {slm_result['headline']}")
            print(f"Recipe:   {slm_result['recipe_title']}")
            print(f"Prep Time: {slm_result['prep_time_mins']} mins")
            print(f"Ingredients: {', '.join(slm_result['ingredients'])}")
        
        print("\nLive SLM integration test complete!")