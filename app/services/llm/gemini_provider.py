import json
import logging
import re
from typing import Dict, List, Tuple
import httpx
from app.core.config import settings
from app.domain.recipes import CustomFinish, Recipe
from app.domain.recommendations import IndividualClinicalRationale
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini Clinical Reasoning Provider.
    Supports Gemini Developer API keys via `x-goog-api-key` without transmitting user PII.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY.strip()
        self.model = settings.GEMINI_MODEL.strip() or "gemini-2.5-flash"
        self.base_url = (
            settings.GEMINI_BASE_URL.strip().rstrip("/")
            or "https://generativelanguage.googleapis.com/v1beta"
        )
        self._fallback = MockLLMProvider()
        self.last_provider_used = "gemini"

    async def generate_clinical_reasoning(
        self,
        recipe: Recipe,
        contexts: list,
        assigned_finishes: Dict[str, CustomFinish],
    ) -> Tuple[str, List[IndividualClinicalRationale]]:
        if not self.api_key:
            logger.info("GEMINI_API_KEY not configured. Falling back to deterministic clinical provider.")
            self.last_provider_used = "mock"
            return await self._fallback.generate_clinical_reasoning(recipe, contexts, assigned_finishes)

        member_key_map: Dict[str, Tuple[object, str]] = {}
        serialized_members = []

        for idx, ctx in enumerate(contexts):
            member_key = f"M{idx + 1}"
            first_name = (ctx.user.full_name or "Member").strip().split()[0]
            member_key_map[member_key] = (ctx, first_name)

            finish = assigned_finishes.get(ctx.user.id)
            serialized_members.append(
                {
                    "member_key": member_key,
                    "diet_preference": ctx.user.diet_preference,
                    "abnormal_biomarkers": [obs.model_dump(mode="json") for obs in ctx.abnormals],
                    "custom_finish": finish.model_dump(mode="json") if finish else None,
                }
            )

        prompt_payload = {
            "recipe": {
                "title": recipe.title,
                "description": recipe.description,
                "calories": recipe.calories,
                "protein_g": recipe.protein_g,
                "net_carbs_g": recipe.net_carbs_g,
                "fiber_g": recipe.fiber_g,
                "saturated_fat_g": recipe.saturated_fat_g,
                "glycemic_load": recipe.glycemic_load,
                "base_ingredients": [ing.model_dump(mode="json") for ing in recipe.base_ingredients],
            },
            "diners": serialized_members,
        }

        system_prompt = (
            "You are an expert clinical nutrition scientist and metabolomics physician for SortMyPlate. "
            "Explain precisely why the selected recipe (plus each diner's custom finishing topping) supports their blood biomarkers. "
            "Notice diners are de-identified as M1, M2, etc. When referencing diners in text, use their exact member_key token (e.g. M1). "
            "Return ONLY valid JSON matching this schema: "
            "{\"overall_summary\": str, \"individual_rationales\": [{\"member_key\": str, \"action\": str, \"mechanism\": str}]}"
        )

        endpoint = f"{self.base_url}/models/{self.model}:generateContent"

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": json.dumps(prompt_payload)}],
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.2,
                            "responseMimeType": "application/json",
                            "maxOutputTokens": 2048,
                        },
                    },
                )

            if response.status_code != 200:
                logger.warning(f"Gemini API error {response.status_code}: {response.text[:300]}")
                self.last_provider_used = "mock"
                return await self._fallback.generate_clinical_reasoning(recipe, contexts, assigned_finishes)

            raw_data = response.json()
            candidates = raw_data.get("candidates") or []
            parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
            text_chunks = [
                p.get("text", "")
                for p in parts
                if isinstance(p, dict) and not p.get("thought") and p.get("text")
            ]
            text_content = "\n".join(text_chunks).strip()
            if "```json" in text_content:
                text_content = text_content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in text_content:
                text_content = text_content.split("```", 1)[1].split("```", 1)[0].strip()

            parsed = json.loads(text_content)
            overall_summary = _rehydrate_member_names(
                str(parsed.get("overall_summary") or "").strip(),
                member_key_map,
            )

            rationales_by_key = {}
            for item in parsed.get("individual_rationales") or []:
                if isinstance(item, dict) and item.get("member_key"):
                    rationales_by_key[str(item["member_key"]).strip()] = item

            rationales: List[IndividualClinicalRationale] = []
            for idx, ctx in enumerate(contexts):
                member_key = f"M{idx + 1}"
                user = ctx.user
                match = rationales_by_key.get(member_key, {})
                finish = assigned_finishes.get(user.id)
                finish_text = (
                    f"Add {finish.name} ({', '.join(i.name for i in finish.ingredients)}) - {finish.mechanism_benefit}"
                    if finish
                    else "Standard shared base serving is optimal."
                )
                target_strings = [
                    f"{obs.display_name} ({obs.numeric_value} {obs.unit})"
                    for obs in ctx.abnormals
                ]

                action_text = _rehydrate_member_names(
                    str(match.get("action") or "Metabolic Maintenance & Energy Stability").strip(),
                    member_key_map,
                )
                mechanism_text = _rehydrate_member_names(
                    str(match.get("mechanism") or "Balanced macronutrient pacing supporting metabolic resilience.").strip(),
                    member_key_map,
                )

                rationales.append(
                    IndividualClinicalRationale(
                        member_id=user.id,
                        member_name=user.full_name,
                        targeted_biomarkers=target_strings if target_strings else ["All Biomarkers Within Normal Range"],
                        action=action_text,
                        mechanism=mechanism_text,
                        suggested_custom_finish=finish_text,
                    )
                )

            if not overall_summary:
                overall_summary = (
                    f"Selected '{recipe.title}' tailored via Gemini clinical nutrition analysis."
                )

            self.last_provider_used = "gemini"
            return overall_summary, rationales

        except Exception as exc:
            logger.error(f"Gemini clinical call failed: {exc}. Falling back to deterministic clinical engine.")
            self.last_provider_used = "mock"
            return await self._fallback.generate_clinical_reasoning(recipe, contexts, assigned_finishes)


def _rehydrate_member_names(text: str, member_key_map: Dict[str, Tuple[object, str]]) -> str:
    result = text
    for key in sorted(member_key_map.keys(), key=len, reverse=True):
        _, first_name = member_key_map[key]
        result = re.sub(rf"\b{re.escape(key)}\b", first_name, result)
    return result
