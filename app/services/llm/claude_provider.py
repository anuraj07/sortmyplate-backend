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

class ClaudeProvider(BaseLLMProvider):
    """
    Anthropic Claude 3.5 Sonnet / Haiku Provider.
    Supports Anthropic API and AWS Bedrock / GCP Vertex AI endpoints.
    """
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self._fallback = MockLLMProvider()

    async def generate_clinical_reasoning(
        self,
        recipe: Recipe,
        contexts: list,
        assigned_finishes: Dict[str, CustomFinish]
    ) -> Tuple[str, List[IndividualClinicalRationale]]:
        if not self.api_key:
            logger.info("ANTHROPIC_API_KEY not set. Using deterministic clinical provider.")
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
            "You must return ONLY raw JSON conforming to this schema: "
            "{\"overall_summary\": \"...\", \"individual_rationales\": [{\"member_name\": \"...\", \"action\": \"...\", \"mechanism\": \"...\"}]}"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-3-5-haiku-20241022",
                        "max_tokens": 1024,
                        "temperature": 0.2,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": json.dumps(prompt_payload)}
                        ]
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    text_content = data["content"][0]["text"]
                    # Extract JSON block if wrapped
                    if "```json" in text_content:
                        text_content = text_content.split("```json")[1].split("```")[0].strip()
                    elif "```" in text_content:
                        text_content = text_content.split("```")[1].split("```")[0].strip()

                    content = json.loads(text_content.strip())
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
                                mechanism=match.get("mechanism", "Balanced nutrition.") if match else "Balanced nutrition.",
                                suggested_custom_finish=finish_text
                            )
                        )
                    return overall_summary, rationales
                else:
                    logger.warning(f"Claude API returned status {response.status_code}: {response.text}")
                    return await self._fallback.generate_clinical_reasoning(recipe, contexts, assigned_finishes)

        except Exception as e:
            logger.error(f"Claude API failed: {e}. Falling back.")
            return await self._fallback.generate_clinical_reasoning(recipe, contexts, assigned_finishes)
