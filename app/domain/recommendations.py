from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from app.domain.recipes import Ingredient, CustomFinish

class NextMealRequest(BaseModel):
    group_id: Optional[str] = None
    active_member_ids: Optional[List[str]] = Field(
        default=None,
        description="IDs of members eating this meal. If omitted, uses all members in group_id or just the current user."
    )
    meal_slot: Optional[str] = Field(
        default="LUNCH", # BREAKFAST, LUNCH, DINNER, SNACK
        description="Desired meal slot. Defaults to time-based or LUNCH."
    )
    max_prep_time_minutes: Optional[int] = 35
    dining_mode: str = "HOME_COOKING"

class IndividualClinicalRationale(BaseModel):
    member_id: str
    member_name: str
    targeted_biomarkers: List[str] # e.g. ["ApoB (118 mg/dL)", "Ferritin (18 ng/mL)"]
    action: str
    mechanism: str
    suggested_custom_finish: Optional[str] = None

class NextMealResponse(BaseModel):
    meal_id: str
    title: str
    description: str
    meal_slot: str
    prep_time_minutes: int
    participating_members: List[str]
    allergens_strictly_avoided: List[str]
    macros_per_serving: Dict[str, float]
    shared_base_ingredients: List[Ingredient]
    prep_instructions: List[str]
    member_customizations: List[IndividualClinicalRationale]
    overall_consensus_reasoning: str
    llm_provider_used: str
