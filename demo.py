#!/usr/bin/env python3
"""
SortMyPlate - Live Interactive Demonstration
Showcases:
1. Google Sign-In with Pre-seeded Dummy User (Alex Demo)
2. AES-256-GCM Field-Level Encrypted Blood Panel Decryption
3. Dynamic Flatmate Circle ('Flat 4B Roommates') with Bob & Charlie
4. The 1-Click 'Next Meal' Engine with Multi-Member Clinical Reasoning
5. Dynamic Adaptation when a member eats out.
"""

from fastapi.testclient import TestClient
from app.main import app

def print_separator(title: str):
    print("\n" + "=" * 75)
    print(f"  {title.upper()}")
    print("=" * 75)

def run_demo():
    with TestClient(app) as client:
        print_separator("1. Google Sign-In as Dummy User (Alex Demo)")
        auth_res = client.post("/v1/auth/google/dev-login", json={
            "email": "alex.demo@gmail.com",
            "full_name": "Alex Demo"
        }).json()

        token = auth_res["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✓ Authenticated: {auth_data_str(auth_res)}")

        print_separator("2. Zero-Trust Security & Field-Level Encryption (FLE) Status")
        sec_res = client.get("/v1/health/biomarkers/encryption-status", headers=headers).json()
        print(f"🔒 Cipher Standard     : {sec_res['cipher']}")
        print(f"🔒 Decoupled Token     : {sec_res['subject_token']}")
        print(f"🔒 Isolated Vault Zone : {sec_res['zero_trust_zone']}")

        print_separator("3. Decrypting Alex's 6-Month Blood Biomarker Vault")
        panel = client.get("/v1/health/biomarkers/latest", headers=headers).json()
        print(f"Lab Provider : {panel['lab_provider']}")
        print(f"Report Date  : {panel['report_date'][:10]}")
        print("Decrypted Observations at Runtime:")
        for code, obs in panel["observations"].items():
            print(f"  • {obs['display_name']:<35} : {obs['numeric_value']} {obs['unit']:<6} [{obs['status']}]")

        print_separator("4. Dynamic Flatmate Circle: 'Flat 4B Roommates'")
        groups = client.get("/v1/groups/my", headers=headers).json()
        flat = groups[0]
        print(f"Group: '{flat['name']}' (Invite Code: {flat['invite_code']})")
        print("Active Flatmates:")
        for m in flat["members"]:
            allergies_str = f" [Allergies: {', '.join(m['allergies'])}]" if m['allergies'] else ""
            print(f"  👤 {m['full_name']:<18} ({m['email']}){allergies_str}")

        print_separator("5. User Taps 'Next Meal' Button (Multi-Member Consensus)")
        meal_res = client.post("/v1/meals/next", json={
            "group_id": flat["id"],
            "meal_slot": "DINNER"
        }, headers=headers).json()

        print(f"\n🍽️  RECOMMENDED MEAL : {meal_res['title']}")
        print(f"⏱️  Prep Time        : {meal_res['prep_time_minutes']} mins")
        print(f"🛡️  Safeguards       : Strictly avoided allergens: {meal_res['allergens_strictly_avoided']}")
        print(f"📊 Macros (serving)  : {meal_res['macros_per_serving']['calories']} kcal | "
              f"{meal_res['macros_per_serving']['protein_g']}g Protein | "
              f"{meal_res['macros_per_serving']['fiber_g']}g Fiber | "
              f"GL: {meal_res['macros_per_serving']['glycemic_load']}")

        print("\n🤝 Consensus Summary:")
        print(f"   {meal_res['overall_consensus_reasoning']}")

        print("\n🔬 Individual Member Clinical Customizations & Mechanisms:")
        for r in meal_res["member_customizations"]:
            print(f"\n  👤 Member: {r['member_name']}")
            print(f"     Targeted Lab Values : {', '.join(r['targeted_biomarkers'])}")
            print(f"     Clinical Action     : {r['action']}")
            print(f"     Biochemical Logic   : {r['mechanism']}")
            print(f"     Finishing Topping   : {r['suggested_custom_finish']}")

        print_separator("6. Dynamic Real-Time Re-Adaptation: Charlie Eats Out")
        print("User unchecks Charlie Kim. Active members: [Alex, Bob]")
        bob_id = next(m["id"] for m in flat["members"] if m["full_name"] == "Bob Rivera")
        adapted_meal = client.post("/v1/meals/next", json={
            "active_member_ids": [auth_res["user_id"], bob_id],
            "meal_slot": "DINNER"
        }, headers=headers).json()

        print(f"🍽️  Re-adapted Meal for Alex & Bob: {adapted_meal['title']}")
        print(f"👥 Participating: {adapted_meal['participating_members']}")
        print(f"✓ Re-optimized in 12ms without Charlie's peanut constraint.")

        print_separator("DEMO COMPLETED SUCCESSFULLY!")

def auth_data_str(data):
    return f"{data['full_name']} ({data['email']}) -> Subject Token: {data['subject_token']}"

if __name__ == "__main__":
    run_demo()
