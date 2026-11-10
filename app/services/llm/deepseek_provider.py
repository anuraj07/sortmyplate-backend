import json
import logging
from typing import List, Dict, Tuple
import httpx
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mock_provider import MockLLMProvider
from app.domain.recipes import Recipe, CustomFinish
from app.domain.recommendations import IndividualClinicalRationale
from app.core.config import settings

logger = logging.getLogger(__name__)

class DeepSeekProvider(BaseLLMProvider):
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL
        self._fallback = MockLLMProvider()

    async def generate_clinical_reasoning(
        self,
        recipe: Recipe,
        contexts: list,
        assigned_finishes: Dict[str, CustomFinish]
    ) -> Tuple[str, List[IndividualClinicalRationale]]:
        if not self.api_key:
            logger.info("DEEPSEEK_API_KEY not configured. Falling back to deterministic clinical provider.")
            return await self._fallback.generate_clinical_reasoning(recipe, contexts, assigned_finishes)

        prompt_payload = {
            "recipe": recipe.model_dump(),
            "members": [
                {
                    "name": ctx.user.full_name,
                    "abnormal_biomarkers": [obs.model_dump() for obs in ctx.abnormals],
                    "custom_finish": assigned_finishes[ctx.user.id].model_dump() if ctx.user.id in assigned_finishes else None
                }
                for ctx in contexts
            ]
        }

        system_prompt = (
            "You are an expert clinical nutrition scientist and metabolomics physician. "
            "Explain precisely why this recommended meal benefits each participating member based on their specific blood biomarkers. "
            "Output JSON with schema: {'overall_summary': str, 'individual_rationales': [{'member_name': str, 'action': str, 'mechanism': str}]}"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat", # DeepSeek-V3
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(prompt_payload)}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    content = json.loads(data["choices"][0]["message"]["content"])
                    overall_summary = content.get("overall_summary", "")
                    
                    rationales = []
                    for ctx in contexts:
                        user = ctx.user
                        match = next((r for r in content.get("individual_rationales", []) if r.get("member_name") == user.full_name), None)
                        finish = assigned_finishes.get(user.id)
                        finish_text = f"Add {finish.name} ({', '.join(i.name for i in finish.ingredients)})" if finish else None
                        
                        target_strings = [f"{obs.display_name} ({obs.numeric_value} {obs.unit})" for obs in ctx.abnormals]
                        
                        rationales.append(
                            IndividualClinicalRationale(
                                member_id=user.id,
                                member_name=user.full_name,
                                targeted_biomarkers=target_strings if target_strings else ["Normal Range"],
                                action=match.get("action", "Metabolic Homeostasis") if match else "Metabolic Balance",
                                mechanism=match.get("mechanism", "Optimized macronutrient pacing.") if match else "Balanced digestion.",
                                suggested_custom_finish=finish_text
                            )
                        )
                    return overall_summary, rationales
                else:
                    logger.warning(f"DeepSeek API error {response.status_code}: {response.text}")
                    return await self._fallback.generate_clinical_reasoning(recipe, contexts, assigned_finishes)

        except Exception as e:
            logger.error(f"DeepSeek call failed: {e}. Using deterministic clinical fallback.")
            return await self._fallback.generate_clinical_reasoning(recipe, contexts, assigned_finishes)
