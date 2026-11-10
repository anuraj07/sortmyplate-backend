from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import UserDB
from app.domain.recommendations import NextMealRequest, NextMealResponse
from app.repositories.user_repo import user_repo
from app.repositories.group_repo import group_repo
from app.services.consensus_engine import consensus_engine
from app.services.llm.factory import get_llm_provider
from app.core.config import settings
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/next", response_model=NextMealResponse)
async def get_next_meal(
    body: NextMealRequest,
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    The Core 1-Click 'Next Meal' Engine.
    Evaluates participating individuals, intersects hard allergy/diet constraints,
    balances longitudinal blood panel targets (decrypted on demand from the PHI Vault),
    and generates multi-member clinical reasoning.
    """
    participating_users: List[UserDB] = []

    # 1. Determine participating members
    if body.active_member_ids and len(body.active_member_ids) > 0:
        for uid in body.active_member_ids:
            u = await user_repo.get_by_id(session, uid)
            if not u:
                raise HTTPException(status_code=404, detail=f"Member '{uid}' not found")
            participating_users.append(u)
    elif body.group_id:
        group = await group_repo.get_by_id(session, body.group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        members = await group_repo.get_group_members(session, body.group_id)
        if not any(m.id == current_user.id for m in members):
            raise HTTPException(status_code=403, detail="You are not a member of this group")
        participating_users = members
    else:
        # Solo eating mode
        participating_users = [current_user]

    if not participating_users:
        participating_users = [current_user]

    # 2. Run multi-member clinical consensus algorithm
    try:
        best_recipe, all_allergens, contexts, assigned_finishes = await consensus_engine.select_best_meal(
            session=session,
            users=participating_users,
            meal_slot=body.meal_slot or "LUNCH",
            max_prep_time=body.max_prep_time_minutes or 35
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 3. Generate clinical reasoning via configured LLM provider
    llm = get_llm_provider()
    group_summary, individual_rationales = await llm.generate_clinical_reasoning(
        recipe=best_recipe,
        contexts=contexts,
        assigned_finishes=assigned_finishes
    )

    # 4. Assemble response
    macros = {
        "calories": float(best_recipe.calories),
        "protein_g": best_recipe.protein_g,
        "net_carbs_g": best_recipe.net_carbs_g,
        "fat_g": best_recipe.fat_g,
        "fiber_g": best_recipe.fiber_g,
        "saturated_fat_g": best_recipe.saturated_fat_g,
        "glycemic_load": best_recipe.glycemic_load
    }

    return NextMealResponse(
        meal_id=best_recipe.id,
        title=best_recipe.title,
        description=best_recipe.description,
        meal_slot=body.meal_slot or "LUNCH",
        prep_time_minutes=best_recipe.prep_time_minutes,
        participating_members=[u.full_name for u in participating_users],
        allergens_strictly_avoided=list(all_allergens),
        macros_per_serving=macros,
        shared_base_ingredients=best_recipe.base_ingredients,
        prep_instructions=best_recipe.prep_instructions,
        member_customizations=individual_rationales,
        overall_consensus_reasoning=group_summary,
        llm_provider_used=getattr(llm, "last_provider_used", settings.LLM_PROVIDER)
    )
