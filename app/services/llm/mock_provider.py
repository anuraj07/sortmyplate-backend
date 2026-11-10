from typing import List, Dict, Tuple
from app.services.llm.base import BaseLLMProvider
from app.domain.recipes import Recipe, CustomFinish
from app.domain.recommendations import IndividualClinicalRationale

BIOMARKER_MECHANISMS = {
    "APOB": (
        "Lowering Circulating Atherogenic Particles",
        "Soluble fiber binds intestinal bile acids, forcing hepatic uptake of ApoB-containing LDL particles; plant sterols and monounsaturated fats lower hepatic VLDL synthesis."
    ),
    "LDL_C": (
        "Decreasing Atherogenic LDL Concentration",
        "Low saturated fatty acid threshold (< 2g/serving) combined with soluble beta-glucan downregulates PCSK9, enhancing LDL receptor density."
    ),
    "HBA1C": (
        "Suppressing Postprandial Glucose Excursions",
        "The meal's low Glycemic Load (GL <= 8.5) and high resistant starch content blunt gastric emptying rates, stabilizing insulin sensitivity."
    ),
    "FASTING_GLUCOSE": (
        "Improving Insulin Sensitivity",
        "High intact fiber-to-carbohydrate ratio buffers intestinal glucose absorption, preventing hepatic gluconeogenesis surges."
    ),
    "FERRITIN": (
        "Maximizing Non-Heme Iron Absorption",
        "Ascorbic acid (Vitamin C) reduces ferric iron (Fe3+) to highly absorbable ferrous iron (Fe2+), boosting non-heme iron uptake by up to 300%."
    ),
    "HS_CRP": (
        "Systemic NF-kB Downregulation",
        "Bioactive polyphenols, curcuminoids, and virgin olive oil fatty acids inhibit COX-2 and IL-6 expression, accelerating CRP normalization."
    ),
    "URIC_ACID": (
        "Preventing Hyperuricemia Excursions",
        "Low-purine plant proteins protect renal uric acid clearance pathways while maintaining adequate amino acid supply."
    )
}

class MockLLMProvider(BaseLLMProvider):
    async def generate_clinical_reasoning(
        self,
        recipe: Recipe,
        contexts: list,
        assigned_finishes: Dict[str, CustomFinish]
    ) -> Tuple[str, List[IndividualClinicalRationale]]:
        
        member_names = [c.user.full_name for c in contexts]
        if len(member_names) == 1:
            group_summary = f"Selected '{recipe.title}' as the optimal solitary meal tailored precisely to {member_names[0]}'s latest metabolic panel."
        else:
            group_summary = (
                f"Multi-member consensus recipe: '{recipe.title}' safely balances dietary constraints across "
                f"{', '.join(member_names)} with a shared low-glycemic, cardioprotective base and personalized finishing toppings."
            )

        rationales: List[IndividualClinicalRationale] = []

        for ctx in contexts:
            user = ctx.user
            abnormals = ctx.abnormals
            target_strings = [f"{obs.display_name} ({obs.numeric_value} {obs.unit})" for obs in abnormals]
            
            # Find mechanisms matching their abnormal markers
            matched_mechanisms = []
            matched_actions = []
            for obs in abnormals:
                code = obs.code.upper()
                if code in BIOMARKER_MECHANISMS:
                    action, mech = BIOMARKER_MECHANISMS[code]
                    matched_actions.append(action)
                    matched_mechanisms.append(f"{obs.display_name}: {mech}")

            finish = assigned_finishes.get(user.id)
            finish_text = f"Add {finish.name} ({', '.join(i.name for i in finish.ingredients)}) - {finish.mechanism_benefit}" if finish else "Standard shared base serving is optimal."

            if not matched_mechanisms:
                action_text = "Metabolic Maintenance & Energy Stability"
                mechanism_text = "Balanced macronutrient distribution supporting stable circadian glycemic control and cellular repair."
            else:
                action_text = "; ".join(matched_actions[:2])
                mechanism_text = " ".join(matched_mechanisms)

            rationales.append(
                IndividualClinicalRationale(
                    member_id=user.id,
                    member_name=user.full_name,
                    targeted_biomarkers=target_strings if target_strings else ["All Biomarkers Within Normal Range"],
                    action=action_text,
                    mechanism=mechanism_text,
                    suggested_custom_finish=finish_text
                )
            )

        return group_summary, rationales
