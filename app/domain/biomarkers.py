import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field

class BiomarkerStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    NORMAL = "NORMAL"
    LOW = "LOW"
    HIGH = "HIGH"
    CRITICAL_LOW = "CRITICAL_LOW"
    CRITICAL_HIGH = "CRITICAL_HIGH"

class ReferenceInterval(BaseModel):
    low: Optional[float] = None
    high: Optional[float] = None

class BiomarkerObservation(BaseModel):
    code: str # Key identifier, e.g. "HBA1C", "APOB", "FERRITIN", "LDL_C"
    loinc_code: Optional[str] = None
    display_name: str
    category: str # "Lipid Panel", "Glycemic Control", "Iron Status", "Inflammation", etc.
    numeric_value: float
    unit: str
    reference_interval: ReferenceInterval
    status: BiomarkerStatus = BiomarkerStatus.NORMAL

class BiomarkerPanelRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"panel_{uuid.uuid4().hex[:10]}")
    subject_token: str # De-identified link to User
    report_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lab_provider: str = "Standard Diagnostics"
    observations: Dict[str, BiomarkerObservation] # Map code -> BiomarkerObservation

class BiomarkerUploadRequest(BaseModel):
    lab_provider: Optional[str] = "Quest/LabCorp"
    observations: List[BiomarkerObservation]

def evaluate_status(code: str, value: float) -> BiomarkerStatus:
    """
    Evaluates clinical reference ranges for primary metabolic markers.
    """
    code_upper = code.upper()
    
    if code_upper in ["HBA1C", "4548-4"]:
        if value < 5.7: return BiomarkerStatus.OPTIMAL
        if value < 6.5: return BiomarkerStatus.HIGH # Prediabetes
        return BiomarkerStatus.CRITICAL_HIGH # Diabetes range
        
    elif code_upper in ["FASTING_GLUCOSE", "1558-6"]:
        if value < 100: return BiomarkerStatus.NORMAL
        if value < 126: return BiomarkerStatus.HIGH
        return BiomarkerStatus.CRITICAL_HIGH
        
    elif code_upper in ["APOB", "1884-6"]:
        if value < 80: return BiomarkerStatus.OPTIMAL
        if value <= 100: return BiomarkerStatus.NORMAL
        return BiomarkerStatus.HIGH
        
    elif code_upper in ["LDL_C", "2089-1"]:
        if value < 100: return BiomarkerStatus.OPTIMAL
        if value <= 130: return BiomarkerStatus.NORMAL
        return BiomarkerStatus.HIGH
        
    elif code_upper in ["FERRITIN", "24331-1"]:
        if value < 30: return BiomarkerStatus.LOW # Latent iron deficiency
        if value <= 200: return BiomarkerStatus.NORMAL
        return BiomarkerStatus.HIGH
        
    elif code_upper in ["HS_CRP", "30934-4"]:
        if value < 1.0: return BiomarkerStatus.OPTIMAL
        if value <= 3.0: return BiomarkerStatus.NORMAL
        return BiomarkerStatus.HIGH
        
    elif code_upper in ["VITAMIN_D3", "62292-8"]:
        if value < 20: return BiomarkerStatus.LOW
        if value < 30: return BiomarkerStatus.NORMAL
        return BiomarkerStatus.OPTIMAL
        
    elif code_upper in ["URIC_ACID", "3084-1"]:
        if value <= 6.5: return BiomarkerStatus.NORMAL
        return BiomarkerStatus.HIGH
        
    return BiomarkerStatus.NORMAL
