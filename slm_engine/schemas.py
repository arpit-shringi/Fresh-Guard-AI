from pydantic import BaseModel, Field
from typing import List

class ItemInput(BaseModel):
    item_id: str
    name: str
    freshness_stage: str 
    original_price: float
    recommended_price: float
    stock_count: int

class SLMGeneratedContent(BaseModel):
    headline: str = Field(description="Catchy flash-sale promotional headline")
    recipe_title: str = Field(description="Title of a zero-waste recipe using the item")
    prep_time_mins: int = Field(description="Estimated preparation time in minutes")
    ingredients: List[str] = Field(description="List of ingredients including the expiring item and basic household staples")
    instructions: List[str] = Field(description="Step-by-step cooking instructions")
    waste_prevented_kg: float = Field(description="Estimated food waste prevented in kg")