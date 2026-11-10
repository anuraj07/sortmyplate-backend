from typing import Dict, List, Optional
from datetime import datetime, timezone
from app.domain.biomarkers import (
    BiomarkerPanelRecord,
    BiomarkerObservation,
    BiomarkerStatus,
    evaluate_status
)

class BiomarkerService:
    def __init__(self):
        self.reset()

    def reset(self):
        # Map subject_token -> List[BiomarkerPanelRecord] sorted by report_date desc
        self._panels_by_subject: Dict[str, List[BiomarkerPanelRecord]] = {}

    def record_panel(
        self,
        subject_token: str,
        observations: List[BiomarkerObservation],
        lab_name: str = "Standard Diagnostics"
    ) -> BiomarkerPanelRecord:
        obs_map: Dict[str, BiomarkerObservation] = {}
        for obs in observations:
            # Re-evaluate status against clinical thresholds if not set
            if obs.status == BiomarkerStatus.NORMAL:
                obs.status = evaluate_status(obs.code, obs.numeric_value)
            obs_map[obs.code.upper()] = obs

        panel = BiomarkerPanelRecord(
            subject_token=subject_token,
            report_date=datetime.now(timezone.utc),
            lab_provider=lab_name,
            observations=obs_map
        )

        if subject_token not in self._panels_by_subject:
            self._panels_by_subject[subject_token] = []
        
        # Insert at front (most recent first)
        self._panels_by_subject[subject_token].insert(0, panel)
        return panel

    def get_latest_panel(self, subject_token: str) -> Optional[BiomarkerPanelRecord]:
        panels = self._panels_by_subject.get(subject_token)
        if panels and len(panels) > 0:
            return panels[0]
        return None

    def get_abnormal_markers(self, subject_token: str) -> List[BiomarkerObservation]:
        panel = self.get_latest_panel(subject_token)
        if not panel:
            return []
        
        abnormals = []
        for obs in panel.observations.values():
            if obs.status in [BiomarkerStatus.HIGH, BiomarkerStatus.CRITICAL_HIGH, 
                              BiomarkerStatus.LOW, BiomarkerStatus.CRITICAL_LOW]:
                abnormals.append(obs)
        return abnormals

biomarker_service = BiomarkerService()
