import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import engine, Base, AsyncSessionLocal
from app.repositories.user_repo import user_repo
from app.repositories.group_repo import group_repo
from app.repositories.biomarker_repo import biomarker_repo
from app.domain.biomarkers import BiomarkerObservation, ReferenceInterval, BiomarkerStatus

logger = logging.getLogger(__name__)

async def init_db_and_seed():
    """
    Creates tables if not present and seeds the pre-configured dummy user and flatmates.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if Alex Demo already exists
        alex = await user_repo.get_by_email(session, "alex.demo@gmail.com")
        if not alex:
            logger.info("Seeding Dummy User (Alex Demo) and flatmates...")
            
            # 1. Seed Alex (Primary user)
            alex = await user_repo.create_or_update_google_user(
                session=session,
                email="alex.demo@gmail.com",
                full_name="Alex Demo",
                google_sub="google_sub_alex_demo_1001",
                picture_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
                allergies=[],
                diet_preference="omnivore"
            )

            # 2. Seed Alex's 6-Month Blood Panel (Encrypted at rest with AES-256-GCM)
            alex_observations = [
                BiomarkerObservation(
                    code="APOB",
                    loinc_code="1884-6",
                    display_name="Apolipoprotein B",
                    category="Lipid Panel",
                    numeric_value=118.0,
                    unit="mg/dL",
                    reference_interval=ReferenceInterval(low=50.0, high=90.0),
                    status=BiomarkerStatus.HIGH
                ),
                BiomarkerObservation(
                    code="LDL_C",
                    loinc_code="2089-1",
                    display_name="LDL Cholesterol",
                    category="Lipid Panel",
                    numeric_value=142.0,
                    unit="mg/dL",
                    reference_interval=ReferenceInterval(low=0.0, high=100.0),
                    status=BiomarkerStatus.HIGH
                ),
                BiomarkerObservation(
                    code="HBA1C",
                    loinc_code="4548-4",
                    display_name="Hemoglobin A1c",
                    category="Glycemic Control",
                    numeric_value=5.8,
                    unit="%",
                    reference_interval=ReferenceInterval(low=4.0, high=5.6),
                    status=BiomarkerStatus.HIGH
                ),
                BiomarkerObservation(
                    code="FERRITIN",
                    loinc_code="24331-1",
                    display_name="Serum Ferritin (Iron Reserve)",
                    category="Iron Panel",
                    numeric_value=18.0,
                    unit="ng/mL",
                    reference_interval=ReferenceInterval(low=30.0, high=200.0),
                    status=BiomarkerStatus.LOW
                ),
                BiomarkerObservation(
                    code="HS_CRP",
                    loinc_code="30934-4",
                    display_name="High-Sensitivity CRP",
                    category="Inflammation",
                    numeric_value=2.8,
                    unit="mg/L",
                    reference_interval=ReferenceInterval(low=0.0, high=1.0),
                    status=BiomarkerStatus.HIGH
                )
            ]
            await biomarker_repo.save_panel(
                session=session,
                subject_token=alex.subject_token,
                observations=alex_observations,
                lab_provider="Quest Diagnostics (October 2026)"
            )

            # 3. Seed Bob Rivera (Flatmate with high LDL)
            bob = await user_repo.create_or_update_google_user(
                session=session,
                email="bob.flatmate@gmail.com",
                full_name="Bob Rivera",
                google_sub="google_sub_bob_1002",
                picture_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
                allergies=[],
                diet_preference="omnivore"
            )
            bob_obs = [
                BiomarkerObservation(
                    code="APOB",
                    loinc_code="1884-6",
                    display_name="Apolipoprotein B",
                    category="Lipid Panel",
                    numeric_value=128.0,
                    unit="mg/dL",
                    reference_interval=ReferenceInterval(low=50.0, high=90.0),
                    status=BiomarkerStatus.HIGH
                )
            ]
            await biomarker_repo.save_panel(session, bob.subject_token, bob_obs, "LabCorp")

            # 4. Seed Charlie Kim (Flatmate with peanut allergy and prediabetic HbA1c)
            charlie = await user_repo.create_or_update_google_user(
                session=session,
                email="charlie.flatmate@gmail.com",
                full_name="Charlie Kim",
                google_sub="google_sub_charlie_1003",
                picture_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
                allergies=["peanuts"],
                diet_preference="omnivore"
            )
            charlie_obs = [
                BiomarkerObservation(
                    code="HBA1C",
                    loinc_code="4548-4",
                    display_name="Hemoglobin A1c",
                    category="Glycemic Control",
                    numeric_value=5.9,
                    unit="%",
                    reference_interval=ReferenceInterval(low=4.0, high=5.6),
                    status=BiomarkerStatus.HIGH
                )
            ]
            await biomarker_repo.save_panel(session, charlie.subject_token, charlie_obs, "Quest Diagnostics")

            # 5. Create Group "Flat 4B Roommates"
            group = await group_repo.create_group(session, owner_id=alex.id, name="Flat 4B Roommates")
            # Set memorable code for demo
            group.invite_code = "FLAT4B"
            await session.commit()

            await group_repo.join_group(session, user_id=bob.id, invite_code="FLAT4B")
            await group_repo.join_group(session, user_id=charlie.id, invite_code="FLAT4B")

            logger.info("Database initialized & seeded successfully!")
