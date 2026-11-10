import pytest
import json
from app.db.base import AsyncSessionLocal
from app.db.models import UserDB
from app.services.consensus_engine import consensus_engine

@pytest.mark.asyncio
async def test_consensus_engine_allergy_elimination():
    async with AsyncSessionLocal() as session:
        user1 = UserDB(
            id="usr_test_1",
            email="u1@test.com",
            full_name="User 1",
            diet_preference="omnivore",
            allergies=json.dumps(["shellfish"]),
            subject_token="sub_test_1"
        )
        user2 = UserDB(
            id="usr_test_2",
            email="u2@test.com",
            full_name="User 2",
            diet_preference="omnivore",
            allergies=json.dumps(["fish"]),
            subject_token="sub_test_2"
        )

        all_allergens, _, contexts = await consensus_engine.resolve_participating_members(session, [user1, user2])
        assert "shellfish" in all_allergens
        assert "fish" in all_allergens
        assert len(contexts) == 2

        best_recipe, eliminated_allergens, _, _ = await consensus_engine.select_best_meal(
            session=session,
            users=[user1, user2],
            meal_slot="DINNER",
            max_prep_time=40
        )
        assert "fish" not in best_recipe.base_allergens
        assert best_recipe.id != "rcp_wild_salmon_sweet_potato"
