import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_dynamic_endpoint_discovery_and_multi_user_meal_flow():
    # Use TestClient with context manager to ensure lifespan runs (creates empty tables)
    with TestClient(app) as client:
        # 1. Verify legacy dev-login demo endpoint is removed
        legacy_resp = client.post("/v1/auth/google/dev-login", json={
            "email": "demo@example.com",
            "full_name": "Demo"
        })
        assert legacy_resp.status_code == 404

        # 2. Frontend Discovery Step: Fetch /bootstrap endpoints for the session
        boot_resp = client.get("/bootstrap")
        assert boot_resp.status_code == 200
        boot = boot_resp.json()
        assert "base_url" in boot
        endpoints = boot["endpoints"]
        for required_key in [
            "health", "llm_status", "auth_google", "auth_me",
            "groups_create", "groups_join", "groups_leave", "groups_my",
            "biomarkers_record", "biomarkers_latest", "meals_next"
        ]:
            assert required_key in endpoints

        # Verify reverse proxy HTTPS upgrade for ramnaymcloud.com
        proxy_boot = client.get(
            "/bootstrap",
            headers={"x-forwarded-host": "j6tgemptpq36.ramnaymcloud.com", "x-forwarded-proto": "https"}
        )
        assert proxy_boot.status_code == 200
        assert proxy_boot.json()["base_url"] == "https://j6tgemptpq36.ramnaymcloud.com"

        # 3. Sign in three real users via discovered auth_google endpoint
        alice_resp = client.post(endpoints["auth_google"], json={
            "email": "alice@gmail.com",
            "name": "Alice Chen",
            "allergies": []
        })
        assert alice_resp.status_code == 200
        alice = alice_resp.json()
        assert alice["email"] == "alice@gmail.com"
        assert alice["subject_token"].startswith("sub_")
        alice_headers = {"Authorization": f"Bearer {alice['access_token']}"}

        bob_resp = client.post(endpoints["auth_google"], json={
            "email": "bob.rivera@gmail.com",
            "name": "Bob Rivera",
            "allergies": []
        })
        assert bob_resp.status_code == 200
        bob = bob_resp.json()
        bob_headers = {"Authorization": f"Bearer {bob['access_token']}"}

        charlie_resp = client.post(endpoints["auth_google"], json={
            "email": "charlie.kim@gmail.com",
            "name": "Charlie Kim",
            "allergies": ["peanuts"]
        })
        assert charlie_resp.status_code == 200
        charlie = charlie_resp.json()
        charlie_headers = {"Authorization": f"Bearer {charlie['access_token']}"}

        # 4. Alice has no pre-seeded blood panel yet (returns 404)
        empty_panel_resp = client.get(endpoints["biomarkers_latest"], headers=alice_headers)
        assert empty_panel_resp.status_code == 404

        # 5. Record encrypted blood biomarkers for Alice and Bob via discovered endpoint
        record_alice = client.post(endpoints["biomarkers_record"], json={
            "lab_provider": "Quest Diagnostics",
            "observations": [
                {
                    "code": "APOB",
                    "loinc_code": "1884-6",
                    "display_name": "Apolipoprotein B (ApoB)",
                    "category": "Lipid Panel",
                    "numeric_value": 118.0,
                    "unit": "mg/dL",
                    "reference_interval": {"low": 40, "high": 90},
                    "status": "NORMAL"
                },
                {
                    "code": "FERRITIN",
                    "loinc_code": "24331-1",
                    "display_name": "Serum Ferritin",
                    "category": "Iron Status",
                    "numeric_value": 18.0,
                    "unit": "ng/mL",
                    "reference_interval": {"low": 30, "high": 200},
                    "status": "NORMAL"
                }
            ]
        }, headers=alice_headers)
        assert record_alice.status_code == 201

        record_bob = client.post(endpoints["biomarkers_record"], json={
            "lab_provider": "LabCorp",
            "observations": [
                {
                    "code": "HBA1C",
                    "loinc_code": "4548-4",
                    "display_name": "Hemoglobin A1c",
                    "category": "Glycemic Control",
                    "numeric_value": 5.9,
                    "unit": "%",
                    "reference_interval": {"low": 4.0, "high": 5.6},
                    "status": "NORMAL"
                }
            ]
        }, headers=bob_headers)
        assert record_bob.status_code == 201

        # Verify Alice's decrypted biomarkers
        panel_resp = client.get(endpoints["biomarkers_latest"], headers=alice_headers)
        assert panel_resp.status_code == 200
        panel = panel_resp.json()
        assert panel["observations"]["APOB"]["numeric_value"] == 118.0
        assert panel["observations"]["APOB"]["status"] == "HIGH"
        assert panel["observations"]["FERRITIN"]["status"] == "LOW"

        # 6. Create Household Group and join members using discovered endpoints
        create_grp_resp = client.post(
            endpoints["groups_create"],
            json={"name": "Flat 4B Roommates"},
            headers=alice_headers
        )
        assert create_grp_resp.status_code == 201
        flat = create_grp_resp.json()
        invite_code = flat["invite_code"]

        join_bob = client.post(
            endpoints["groups_join"],
            json={"invite_code": invite_code},
            headers=bob_headers
        )
        assert join_bob.status_code == 200

        join_charlie = client.post(
            endpoints["groups_join"],
            json={"invite_code": invite_code},
            headers=charlie_headers
        )
        assert join_charlie.status_code == 200
        assert len(join_charlie.json()["members"]) == 3

        # 7. Request Next Meal via discovered meals_next endpoint
        meal_resp = client.post(endpoints["meals_next"], json={
            "group_id": flat["id"],
            "meal_slot": "DINNER"
        }, headers=alice_headers)

        assert meal_resp.status_code == 200
        meal = meal_resp.json()

        # Charlie has peanut allergy -> must be strictly avoided
        assert "peanuts" in meal["allergens_strictly_avoided"]

        # Check customizations for all 3 members
        custom_names = [c["member_name"] for c in meal["member_customizations"]]
        assert "Alice Chen" in custom_names
        assert "Bob Rivera" in custom_names
        assert "Charlie Kim" in custom_names

        alice_custom = next(c for c in meal["member_customizations"] if c["member_name"] == "Alice Chen")
        assert "ApoB" in str(alice_custom["targeted_biomarkers"]) or "Ferritin" in str(alice_custom["targeted_biomarkers"])

        # 8. Test Charlie leaving the group via parameterized discovered endpoint
        leave_path = endpoints["groups_leave"].replace("{group_id}", flat["id"])
        leave_resp = client.post(leave_path, headers=charlie_headers)
        assert leave_resp.status_code == 200

        charlie_groups = client.get(endpoints["groups_my"], headers=charlie_headers)
        assert charlie_groups.status_code == 200
        assert len(charlie_groups.json()) == 0
