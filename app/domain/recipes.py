from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class Ingredient(BaseModel):
    name: str
    amount: str
    unit: str
    allergens: List[str] = Field(default_factory=list) # e.g. ["dairy", "gluten", "peanuts", "soy"]
    tags: List[str] = Field(default_factory=list) # e.g. ["high_soluble_fiber", "resistant_starch", "iron_rich"]

class CustomFinish(BaseModel):
    """
    Personalized topping or dressing added to the shared base dish
    targeting an individual member's specific biomarker imbalance.
    """
    for_biomarker: str # e.g. "FERRITIN", "APOB", "HBA1C", "HS_CRP"
    name: str
    ingredients: List[Ingredient]
    mechanism_benefit: str

class Recipe(BaseModel):
    id: str
    title: str
    description: str
    meal_slots: List[str] # ["BREAKFAST", "LUNCH", "DINNER", "SNACK"]
    diet_types: List[str] # ["omnivore", "vegetarian", "vegan", "pescatarian"]
    prep_time_minutes: int
    difficulty: str = "EASY"
    
    # Nutrition profile per serving
    calories: int
    protein_g: float
    net_carbs_g: float
    fat_g: float
    fiber_g: float
    saturated_fat_g: float
    glycemic_load: float # Low <= 10, Med 11-19, High >= 20
    
    # Allergens present in the shared base
    base_allergens: List[str] = Field(default_factory=list)
    
    # Base ingredients shared by everyone
    base_ingredients: List[Ingredient]
    prep_instructions: List[str]
    
    # Available custom finishes to adjust per person
    custom_finishes: List[CustomFinish] = Field(default_factory=list)
    
    # Biochemical tag flags for algorithm scoring
    is_low_saturated_fat: bool = True
    is_low_glycemic: bool = True
    is_high_soluble_fiber: bool = False
    is_rich_iron: bool = False
    is_high_omega3: bool = False
    is_anti_inflammatory: bool = False
    is_low_purine: bool = True
