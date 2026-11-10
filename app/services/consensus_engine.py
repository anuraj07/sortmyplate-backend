import json
from typing import List, Dict, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import UserDB
from app.domain.recipes import Recipe, CustomFinish
from app.domain.biomarkers import BiomarkerObservation
from app.repositories.biomarker_repo import biomarker_repo
from app.services.recipe_service import recipe_service

class MemberProfileContext:
    def __init__(self, user: UserDB, abnormals: List[BiomarkerObservation]):
        self.user = user
        self.abnormals = abnormals
        self.abnormal_codes: Set[str] = {obs.code.upper() for obs in abnormals}

class ConsensusEngine:
    async def resolve_participating_members(
        self,
        session: AsyncSession,
        users: List[UserDB]
    ) -> Tuple[Set[str], Set[str], List[MemberProfileContext]]:
        """
        Extracts combined safety constraints and biomarker profiles from encrypted DB vault.
        """
        all_allergens: Set[str] = set()
        required_diets: Set[str] = set()
        member_contexts: List[MemberProfileContext] = []

        for user in users:
            allergies_list = json.loads(user.allergies) if user.allergies else []
            for allergen in allergies_list:
                all_allergens.add(allergen.lower().strip())
            
            if user.diet_preference in ["vegan", "vegetarian", "pescatarian"]:
                required_diets.add(user.diet_preference)

            # Decrypts findings on demand for scoring
            abnormals = await biomarker_repo.get_abnormal_markers(session, user.subject_token)
            member_contexts.append(MemberProfileContext(user, abnormals))

        return all_allergens, required_diets, member_contexts

    def score_recipe_for_group(self, recipe: Recipe, contexts: List[MemberProfileContext]) -> float:
        score = 100.0

        total_apob_need = sum(1 for c in contexts if "APOB" in c.abnormal_codes or "LDL_C" in c.abnormal_codes)
        total_hba1c_need = sum(1 for c in contexts if "HBA1C" in c.abnormal_codes or "FASTING_GLUCOSE" in c.abnormal_codes)
        total_ferritin_need = sum(1 for c in contexts if "FERRITIN" in c.abnormal_codes)
        total_hscrp_need = sum(1 for c in contexts if "HS_CRP" in c.abnormal_codes)
        total_uric_acid_need = sum(1 for c in contexts if "URIC_ACID" in c.abnormal_codes)

        if total_apob_need > 0:
            if recipe.is_low_saturated_fat: score += 25.0 * total_apob_need
            if recipe.is_high_soluble_fiber: score += 30.0 * total_apob_need
            if recipe.saturated_fat_g > 4.0: score -= 20.0 * total_apob_need

        if total_hba1c_need > 0:
            if recipe.is_low_glycemic: score += 30.0 * total_hba1c_need
            if recipe.glycemic_load <= 10.0: score += 20.0 * total_hba1c_need
            if recipe.glycemic_load > 15.0: score -= 30.0 * total_hba1c_need

        if total_ferritin_need > 0:
            if recipe.is_rich_iron: score += 25.0 * total_ferritin_need

        if total_hscrp_need > 0:
            if recipe.is_anti_inflammatory: score += 25.0 * total_hscrp_need

        if total_uric_acid_need > 0:
            if not recipe.is_low_purine: score -= 45.0 * total_uric_acid_need

        for context in contexts:
            for finish in recipe.custom_finishes:
                if finish.for_biomarker in context.abnormal_codes:
                    score += 15.0

        return score

    async def select_best_meal(
        self,
        session: AsyncSession,
        users: List[UserDB],
        meal_slot: str,
        max_prep_time: int
    ) -> Tuple[Recipe, Set[str], List[MemberProfileContext], Dict[str, CustomFinish]]:
        all_allergens, required_diets, contexts = await self.resolve_participating_members(session, users)
        
        candidates = recipe_service.find_eligible_recipes(
            banned_allergens=all_allergens,
            required_diet_types=required_diets,
            meal_slot=meal_slot,
            max_prep_time=max_prep_time
        )

        if not candidates:
            candidates = recipe_service.find_eligible_recipes(
                banned_allergens=all_allergens,
                required_diet_types=required_diets,
                meal_slot=meal_slot,
                max_prep_time=max_prep_time + 15
            )

        if not candidates:
            raise ValueError(f"No safe recipe found matching allergen constraints: {list(all_allergens)}")

        scored = [(r, self.score_recipe_for_group(r, contexts)) for r in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        best_recipe = scored[0][0]

        assigned_finishes: Dict[str, CustomFinish] = {}
        for context in contexts:
            for finish in best_recipe.custom_finishes:
                if finish.for_biomarker in context.abnormal_codes:
                    assigned_finishes[context.user.id] = finish
                    break

        return best_recipe, all_allergens, contexts, assigned_finishes

consensus_engine = ConsensusEngine()
