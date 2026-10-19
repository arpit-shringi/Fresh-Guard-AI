import json
from slm_engine.schemas import ItemInput, SLMGeneratedContent

SYSTEM_PROMPT = """You are FreshGuard SLM, an AI specialized in sustainable retail merchandising.
Your job is to generate contextual promotional copy and simple zero-waste recipes for store items near expiry or overstocked.

STRICT CONSTRAINTS:
1. You MUST NEVER calculate or alter prices. Use the recommended price as given.
2. You MUST return ONLY valid JSON matching the requested structure.
3. Keep recipes extremely simple (3-5 basic ingredients, under 15 mins prep time).
"""

def generate_promo_and_recipe(item: ItemInput) -> dict:

    user_prompt = f"""
    Item: {item.name}
    Status: {item.freshness_stage}
    Stock Count: {item.stock_count} units
    Original Price: ${item.original_price:.2f}
    Flash Sale Price: ${item.recommended_price:.2f}

    Generate a catchy promo headline and a quick zero-waste recipe using {item.name}.
    Return output strictly in JSON format matching the schema.
    """
    
    mock_slm_response = {
        "headline": f"Flash Sale: Save big on fresh {item.name}s today!",
        "recipe_title": f"Quick & Easy {item.name} Delight",
        "prep_time_mins": 10,
        "ingredients": [f"2 {item.name}s", "1 tbsp Olive Oil", "Salt & Pepper to taste"],
        "instructions": [f"Slice the {item.name}s evenly.", "Toss with olive oil and seasoning.", "Serve fresh immediately."],
        "waste_prevented_kg": round(item.stock_count * 0.15, 2)
    }

    validated_output = SLMGeneratedContent(**mock_slm_response)
    return validated_output.model_dump()

if __name__ == "__main__":
    
    sample_item = ItemInput(
        item_id="prod_101",
        name="Avocado",
        freshness_stage="Near Expiry",
        original_price=2.50,
        recommended_price=1.50,
        stock_count=10
    )
    result = generate_promo_and_recipe(sample_item)
    print("SLM Engine Local Test Result:")
    print(json.dumps(result, indent=2))