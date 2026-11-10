from typing import Optional, List, Dict
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models import BiomarkerPanelDB
from app.domain.biomarkers import (
    BiomarkerObservation,
    BiomarkerPanelRecord,
    BiomarkerStatus,
    evaluate_status
)
from app.core.crypto import fle_service

class BiomarkerRepository:
    async def save_panel(
        self,
        session: AsyncSession,
        subject_token: str,
        observations: List[BiomarkerObservation],
        lab_provider: str = "Standard Diagnostics",
        report_date: Optional[datetime] = None
    ) -> BiomarkerPanelRecord:
        obs_dict: Dict[str, dict] = {}
        for obs in observations:
            if obs.status == BiomarkerStatus.NORMAL:
                obs.status = evaluate_status(obs.code, obs.numeric_value)
            obs_dict[obs.code.upper()] = obs.model_dump()

        # Encrypt the entire clinical payload at rest using AES-256-GCM
        encrypted_payload = fle_service.encrypt_json(obs_dict)

        panel_db = BiomarkerPanelDB(
            subject_token=subject_token,
            lab_provider=lab_provider,
            report_date=report_date or datetime.now(timezone.utc),
            encrypted_payload=encrypted_payload
        )
        session.add(panel_db)
        await session.commit()
        await session.refresh(panel_db)

        # Convert back to domain model
        obs_models = {k: BiomarkerObservation(**v) for k, v in obs_dict.items()}
        return BiomarkerPanelRecord(
            id=panel_db.id,
            subject_token=subject_token,
            report_date=panel_db.report_date,
            lab_provider=panel_db.lab_provider,
            observations=obs_models
        )

    async def get_latest_panel(self, session: AsyncSession, subject_token: str) -> Optional[BiomarkerPanelRecord]:
        stmt = (
            select(BiomarkerPanelDB)
            .where(BiomarkerPanelDB.subject_token == subject_token)
            .order_by(desc(BiomarkerPanelDB.report_date))
        )
        result = await session.execute(stmt)
        panel_db = result.scalars().first()
        if not panel_db:
            return None

        # Decrypt AES-256-GCM payload
        decrypted_dict = fle_service.decrypt_json(panel_db.encrypted_payload)
        obs_models = {k: BiomarkerObservation(**v) for k, v in decrypted_dict.items()}

        return BiomarkerPanelRecord(
            id=panel_db.id,
            subject_token=panel_db.subject_token,
            report_date=panel_db.report_date,
            lab_provider=panel_db.lab_provider,
            observations=obs_models
        )

    async def get_abnormal_markers(self, session: AsyncSession, subject_token: str) -> List[BiomarkerObservation]:
        panel = await self.get_latest_panel(session, subject_token)
        if not panel:
            return []
        
        abnormals = []
        for obs in panel.observations.values():
            if obs.status in [
                BiomarkerStatus.HIGH, BiomarkerStatus.CRITICAL_HIGH,
                BiomarkerStatus.LOW, BiomarkerStatus.CRITICAL_LOW
            ]:
                abnormals.append(obs)
        return abnormals

biomarker_repo = BiomarkerRepository()
