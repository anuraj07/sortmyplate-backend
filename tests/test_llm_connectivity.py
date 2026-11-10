import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.domain.biomarkers import BiomarkerObservation, BiomarkerStatus, ReferenceInterval
from app.domain.recipes import CustomFinish, Ingredient, Recipe
from app.main import app
from app.services.consensus_engine import MemberProfileContext
from app.services.llm.gemini_provider import GeminiProvider


def test_llm_status_endpoint():
    with TestClient(app) as client:
        res = client.get("/health/llm-status")
        assert res.status_code == 200
        data = res.json()
        assert "provider" in data
        assert "status" in data
        # Default in test environment is "mock"
        assert data["provider"] == "mock"
        assert data["status"] == "ONLINE"


@pytest.mark.asyncio
async def test_gemini_status_and_clinical_reasoning(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    with TestClient(app) as client:
        unconf = client.get("/health/llm-status")
        assert unconf.status_code == 200
        assert unconf.json()["status"] == "UNCONFIGURED"

    captured_payloads = []

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)

        def json(self) -> dict:
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, headers=None):
            assert url.endswith("/models/gemini-2.5-flash")
            assert headers["x-goog-api-key"] == "AQ.fake-test-key"
            return _FakeResponse(200, {"name": "models/gemini-2.5-flash"})

        async def post(self, url: str, headers=None, json=None):
            assert url.endswith("/models/gemini-2.5-flash:generateContent")
            assert headers["x-goog-api-key"] == "AQ.fake-test-key"
            captured_payloads.append(json)
            return _FakeResponse(
                200,
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"thought": True, "text": "internal thought trace"},
                                    {
                                        "text": json_module.dumps(
                                            {
                                                "overall_summary": "This soluble-fiber bowl works cleanly for M1.",
                                                "individual_rationales": [
                                                    {
                                                        "member_key": "M1",
                                                        "action": "Lower ApoB & Balance Glucose",
                                                        "mechanism": "For M1, oat beta-glucan and extra-virgin olive oil support LDL clearance.",
                                                    }
                                                ],
                                            }
                                        )
                                    },
                                ]
                            }
                        }
                    ]
                },
            )

    json_module = json
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AQ.fake-test-key")
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(app) as client:
        status_res = client.get("/health/llm-status")
        assert status_res.status_code == 200
        status_json = status_res.json()
        assert status_json["provider"] == "gemini"
        assert status_json["status"] == "CONNECTED"
        assert status_json["model"] == "gemini-2.5-flash"

    class _StubUser:
        id = "usr_123"
        full_name = "Alice Chen"
        email = "alice.private@gmail.com"
        diet_preference = "pescatarian"

    recipe = Recipe(
        id="rec_test",
        title="Herbed Lentil & Salmon Bowl",
        description="High soluble fiber and omega-3 dinner.",
        meal_slots=["DINNER"],
        diet_types=["pescatarian"],
        prep_time_minutes=20,
        calories=520,
        protein_g=34.0,
        net_carbs_g=28.0,
        fat_g=18.0,
        fiber_g=11.0,
        saturated_fat_g=2.4,
        glycemic_load=7.0,
        base_ingredients=[Ingredient(name="Red lentils", amount="120", unit="g")],
        prep_instructions=["Simmer lentils cleanly."],
    )
    obs = BiomarkerObservation(
        code="APOB",
        loinc_code="1884-6",
        display_name="Apolipoprotein B",
        category="Lipid Panel",
        numeric_value=118.0,
        unit="mg/dL",
        reference_interval=ReferenceInterval(low=40, high=90),
        status=BiomarkerStatus.HIGH,
    )
    finish = CustomFinish(
        for_biomarker="APOB",
        name="Flax & Walnut Crumble",
        ingredients=[Ingredient(name="Ground flaxseed", amount="15", unit="g")],
        mechanism_benefit="Binds bile acids with viscous mucilage.",
    )

    provider = GeminiProvider()
    summary, rationales = await provider.generate_clinical_reasoning(
        recipe=recipe,
        contexts=[MemberProfileContext(_StubUser(), [obs])],
        assigned_finishes={"usr_123": finish},
    )

    assert provider.last_provider_used == "gemini"
    assert "Alice" in summary
    assert "M1" not in summary
    assert len(rationales) == 1
    assert rationales[0].member_name == "Alice Chen"
    assert "Alice" in rationales[0].mechanism
    assert "Flax & Walnut Crumble" in rationales[0].suggested_custom_finish

    # Verify zero email/full_name PII sent to Gemini
    sent_json = json.dumps(captured_payloads[0])
    assert "alice.private@gmail.com" not in sent_json
    assert "Alice Chen" not in sent_json
