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


def test_real_google_oauth_code_exchange_and_replay_protection(monkeypatch):
    from app.core.config import settings
    from app.api.v1 import auth as auth_module

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-google-secret")

    async def fake_exchange(code: str, redirect_uri: str) -> dict:
        assert code == "valid_google_code"
        return {
            "sub": "google-sub-999111",
            "email": "maya.patel@gmail.com",
            "email_verified": True,
            "name": "Maya Patel",
            "picture": "https://lh3.googleusercontent.com/a/maya-avatar",
        }

    monkeypatch.setattr(auth_module, "_exchange_google_code_for_profile", fake_exchange)

    with TestClient(app) as client:
        boot = client.get("/bootstrap").json()
        assert boot["google_oauth_enabled"] is True
        endpoints = boot["endpoints"]

        # Reject open-redirect target outside allowlist
        bad_redirect = client.get(
            endpoints["auth_google_login"],
            params={"state": "client_state_1234567890", "redirect_to": "https://evil.example.com", "response_mode": "json"},
        )
        assert bad_redirect.status_code == 400

        # Initiate OAuth flow via discovered endpoint
        login_res = client.get(
            endpoints["auth_google_login"],
            params={"state": "client_state_1234567890", "platform": "web", "redirect_to": "/", "response_mode": "json"},
        )
        assert login_res.status_code == 200
        auth_url = login_res.json()["auth_url"]
        assert "accounts.google.com/o/oauth2/v2/auth" in auth_url
        assert "scope=openid+email+profile" in auth_url

        # Simulate Google redirecting back to callback
        cb_res = client.get(
            "/v1/auth/google/callback",
            params={"code": "valid_google_code", "state": "client_state_1234567890"},
            follow_redirects=False,
        )
        assert cb_res.status_code == 302
        location = cb_res.headers["location"]
        assert "oauth_state=client_state_1234567890" in location
        exchange_code = location.split("oauth_code=")[1].split("&")[0]

        # Exchange one-time code for JWT + profile fetched from Google
        exchange_res = client.post(
            endpoints["auth_google_exchange"],
            json={"state": "client_state_1234567890", "exchange_code": exchange_code},
        )
        assert exchange_res.status_code == 200
        auth_data = exchange_res.json()
        assert auth_data["email"] == "maya.patel@gmail.com"
        assert auth_data["full_name"] == "Maya Patel"
        assert auth_data["picture_url"] == "https://lh3.googleusercontent.com/a/maya-avatar"
        assert auth_data["access_token"]

        # Replay of consumed state/exchange code must fail
        replay_res = client.post(
            endpoints["auth_google_exchange"],
            json={"state": "client_state_1234567890", "exchange_code": exchange_code},
        )
        assert replay_res.status_code == 409

        # Update allergies & diet preference and verify a second OAuth login preserves them
        upd_res = client.put(
            endpoints["auth_profile"],
            json={"allergies": ["tree nuts"], "diet_preference": "vegetarian"},
            headers={"Authorization": f"Bearer {auth_data['access_token']}"},
        )
        assert upd_res.status_code == 200
        assert upd_res.json()["diet_preference"] == "vegetarian"

        # Second mobile/poll login preserves diet & allergies
        login2 = client.get(
            endpoints["auth_google_login"],
            params={"state": "mobile_state_0987654321", "platform": "wasm", "response_mode": "json"},
        )
        assert login2.status_code == 200
        cb2 = client.get(
            "/v1/auth/google/callback",
            params={"code": "valid_google_code", "state": "mobile_state_0987654321"},
        )
        assert cb2.status_code == 200

        poll_url = endpoints["auth_google_session"].replace("{oauth_state}", "mobile_state_0987654321")
        poll_res = client.get(poll_url)
        assert poll_res.status_code == 200
        polled = poll_res.json()
        assert polled["status"] == "completed"
        assert polled["auth"]["diet_preference"] == "vegetarian"
        assert "tree nuts" in polled["auth"]["allergies"]


def test_in_app_google_id_token_and_access_token_and_static_icons(monkeypatch):
    import httpx
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "inapp-client-123.apps.googleusercontent.com")

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params=None, headers=None):
            if "tokeninfo" in url:
                tok = (params or {}).get("id_token")
                if tok == "valid-id-token":
                    return _FakeResponse(200, {
                        "aud": "inapp-client-123.apps.googleusercontent.com",
                        "sub": "gis-sub-001",
                        "email": "priya.nair@gmail.com",
                        "email_verified": "true",
                        "name": "Priya Nair",
                        "picture": "https://lh3.googleusercontent.com/a/priya",
                    })
                if tok == "unverified-id-token":
                    return _FakeResponse(200, {
                        "aud": "inapp-client-123.apps.googleusercontent.com",
                        "sub": "gis-sub-unv",
                        "email": "unverified@gmail.com",
                        "email_verified": "false",
                        "name": "Unverified",
                    })
                return _FakeResponse(401, {"error": "invalid_token"})

            if "userinfo" in url:
                auth_header = (headers or {}).get("Authorization", "")
                if auth_header == "Bearer valid-google-access-token":
                    return _FakeResponse(200, {
                        "sub": "gis-tok-sub-002",
                        "email": "rohan.mehta@gmail.com",
                        "email_verified": True,
                        "name": "Rohan Mehta",
                        "picture": "https://lh3.googleusercontent.com/a/rohan",
                    })
                return _FakeResponse(401, {"error": "invalid_token"})
            return _FakeResponse(404, {})

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(app) as client:
        boot_resp = client.get("/bootstrap")
        assert boot_resp.status_code == 200
        assert boot_resp.headers.get("cross-origin-opener-policy") == "same-origin-allow-popups"
        boot = boot_resp.json()
        assert boot["google_gis_enabled"] is True

        # 1. Verify in-app id_token sign-in (Credential Manager / GIS One Tap)
        id_res = client.post(boot["endpoints"]["auth_google"], json={"id_token": "valid-id-token"})
        assert id_res.status_code == 200
        priya = id_res.json()
        assert priya["email"] == "priya.nair@gmail.com"
        assert priya["full_name"] == "Priya Nair"
        assert priya["picture_url"] == "https://lh3.googleusercontent.com/a/priya"

        # 2. Unverified Google email must be rejected
        unv_res = client.post(boot["endpoints"]["auth_google"], json={"id_token": "unverified-id-token"})
        assert unv_res.status_code == 401

        # 3. Verify in-app google_access_token sign-in (GIS Token Client)
        tok_res = client.post(
            boot["endpoints"]["auth_google"],
            json={"google_access_token": "valid-google-access-token"},
        )
        assert tok_res.status_code == 200
        rohan = tok_res.json()
        assert rohan["email"] == "rohan.mehta@gmail.com"
        assert rohan["full_name"] == "Rohan Mehta"

        # 4. Verify web icon assets & post-login onboarding HTML structure
        html_res = client.get("/")
        assert html_res.status_code == 200
        assert "/static/favicon.svg" in html_res.text
        assert 'id="onboarding-section"' in html_res.text
        assert "manual-fallback-details" not in html_res.text
        assert "discovery-mini" not in html_res.text
        assert "Read-only OpenID" not in html_res.text
        assert "g_id_signin_container" not in html_res.text
        for static_path in [
            "/static/favicon.svg",
            "/static/icon-192.png",
            "/static/icon-512.png",
            "/static/apple-touch-icon.png",
            "/static/manifest.webmanifest",
        ]:
            asset_res = client.get(static_path)
            assert asset_res.status_code == 200, f"Missing static asset: {static_path}"
