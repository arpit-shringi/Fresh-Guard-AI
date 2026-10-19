from pydantic import BaseModel, Field
from typing import List, Optional

class ItemInput(BaseModel):
    item_id: str
    name: str
    stock_count: int
    shelf_capacity: int
    freshness_score: float
    freshness_stage: str
    cost_price: float
    original_price: float

    recommended_action: Optional[str] = None
    recommended_price: Optional[float] = None

class SLMGeneratedContent(BaseModel):
    headline: str = Field(description="Catchy flash-sale or bundle promotional headline")
    recipe_title: str = Field(description="Title of a zero-waste recipe using the item")
    prep_time_mins: int = Field(description="Estimated preparation time in minutes")
    ingredients: List[str] = Field(description="List of simple household ingredients")
    instructions: List[str] = Field(description="Step-by-step cooking instructions")
    waste_prevented_kg: float = Field(description="Estimated food waste prevented in kg")