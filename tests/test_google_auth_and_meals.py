import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_seeded_alex_demo_and_next_meal():
    # Use TestClient with context manager to ensure lifespan runs
    with TestClient(app) as client:
        # 1. 1-Click Google Sign-In as Alex Demo
        login_resp = client.post("/v1/auth/google/dev-login", json={
            "email": "alex.demo@gmail.com",
            "full_name": "Alex Demo"
        })
        assert login_resp.status_code == 200
        auth_data = login_resp.json()
        assert auth_data["email"] == "alex.demo@gmail.com"
        assert auth_data["full_name"] == "Alex Demo"
        assert auth_data["subject_token"].startswith("sub_")

        token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Check that Alex's blood report was seeded and decrypted successfully
        panel_resp = client.get("/v1/health/biomarkers/latest", headers=headers)
        assert panel_resp.status_code == 200
        panel = panel_resp.json()
        assert "APOB" in panel["observations"]
        assert panel["observations"]["APOB"]["numeric_value"] == 118.0
        assert panel["observations"]["APOB"]["status"] == "HIGH"
        assert panel["observations"]["FERRITIN"]["numeric_value"] == 18.0

        # 3. Check that Alex has group "Flat 4B Roommates" with Bob & Charlie
        groups_resp = client.get("/v1/groups/my", headers=headers)
        assert groups_resp.status_code == 200
        groups = groups_resp.json()
        assert len(groups) >= 1
        flat = groups[0]
        assert flat["name"] == "Flat 4B Roommates"
        assert len(flat["members"]) == 3

        # 4. Tapping "Next Meal" for the Flat
        meal_resp = client.post("/v1/meals/next", json={
            "group_id": flat["id"],
            "meal_slot": "DINNER"
        }, headers=headers)

        assert meal_resp.status_code == 200
        meal = meal_resp.json()

        # Charlie has peanut allergy -> must be strictly avoided
        assert "peanuts" in meal["allergens_strictly_avoided"]

        # Check customizations for all 3 members
        custom_names = [c["member_name"] for c in meal["member_customizations"]]
        assert "Alex Demo" in custom_names
        assert "Bob Rivera" in custom_names
        assert "Charlie Kim" in custom_names

        alex_custom = next(c for c in meal["member_customizations"] if c["member_name"] == "Alex Demo")
        assert "ApoB" in str(alex_custom["targeted_biomarkers"]) or "Ferritin" in str(alex_custom["targeted_biomarkers"])
