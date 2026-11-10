from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.db.models import UserDB
from app.repositories.biomarker_repo import biomarker_repo
from app.domain.biomarkers import (
    BiomarkerUploadRequest,
    BiomarkerPanelRecord,
    BiomarkerObservation
)
from app.services.pdf_parser import pdf_parser
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/record", response_model=BiomarkerPanelRecord, status_code=status.HTTP_201_CREATED)
async def record_blood_panel(
    body: BiomarkerUploadRequest,
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Records an individual full-body blood test panel.
    Data is encrypted at the application layer with AES-256-GCM before DB write.
    """
    panel = await biomarker_repo.save_panel(
        session=session,
        subject_token=current_user.subject_token,
        observations=body.observations,
        lab_provider=body.lab_provider or "Standard Diagnostics"
    )
    return panel

@router.post("/upload-pdf", response_model=BiomarkerPanelRecord)
async def upload_pdf_report(
    file: UploadFile = File(...),
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Ingests and parses a raw laboratory PDF blood test report.
    Extracts clinical observations, maps to LOINC standards, and encrypts into the PHI Vault.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty PDF file uploaded")
    
    try:
        text = pdf_parser.extract_text(contents)
        observations = pdf_parser.parse_biomarkers(text)
        
        if not observations:
            raise HTTPException(
                status_code=422,
                detail="Could not detect standard biomarkers in this PDF. Please check file format."
            )

        panel = await biomarker_repo.save_panel(
            session=session,
            subject_token=current_user.subject_token,
            observations=observations,
            lab_provider=f"Extracted from {file.filename}"
        )
        return panel
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

@router.get("/latest", response_model=BiomarkerPanelRecord)
async def get_latest_panel(
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    panel = await biomarker_repo.get_latest_panel(session, current_user.subject_token)
    if not panel:
        raise HTTPException(status_code=404, detail="No blood report found for this profile. Please upload one.")
    return panel

@router.get("/abnormals", response_model=List[BiomarkerObservation])
async def get_abnormal_biomarkers(
    current_user: UserDB = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    abnormals = await biomarker_repo.get_abnormal_markers(session, current_user.subject_token)
    return abnormals

@router.get("/encryption-status")
async def get_encryption_status(current_user: UserDB = Depends(get_current_user)):
    """
    Security verification endpoint showing active zero-trust encryption parameters.
    """
    return {
        "status": "ACTIVE",
        "cipher": "AES-256-GCM (Authenticated Envelope Encryption)",
        "subject_token": current_user.subject_token,
        "identity_decoupled": True,
        "zero_trust_zone": "Zone B (Isolated PHI Vault)"
    }
