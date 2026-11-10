import re
import io
from typing import List, Tuple, Optional
from pypdf import PdfReader
from app.domain.biomarkers import (
    BiomarkerObservation,
    ReferenceInterval,
    BiomarkerStatus,
    evaluate_status
)

BIOMARKER_PATTERNS = [
    {
        "code": "APOB",
        "loinc_code": "1884-6",
        "display_name": "Apolipoprotein B",
        "category": "Lipid Panel",
        "unit": "mg/dL",
        "ref": ReferenceInterval(low=50.0, high=90.0),
        "regex": r"(?:apolipoprotein\s*b|apo\s*b)[^\d\n]*?(\d+(?:\.\d+)?)"
    },
    {
        "code": "LDL_C",
        "loinc_code": "2089-1",
        "display_name": "LDL Cholesterol",
        "category": "Lipid Panel",
        "unit": "mg/dL",
        "ref": ReferenceInterval(low=0.0, high=100.0),
        "regex": r"(?:ldl\s*(?:cholesterol|calculated|direct)?)[^\d\n]*?(\d+(?:\.\d+)?)"
    },
    {
        "code": "HBA1C",
        "loinc_code": "4548-4",
        "display_name": "Hemoglobin A1c",
        "category": "Glycemic Control",
        "unit": "%",
        "ref": ReferenceInterval(low=4.0, high=5.6),
        "regex": r"(?:hba1c|hemoglobin\s*a1c|glycated\s*hemoglobin)[^\d\n]*?(\d+(?:\.\d+)?)"
    },
    {
        "code": "FASTING_GLUCOSE",
        "loinc_code": "1558-6",
        "display_name": "Fasting Blood Glucose",
        "category": "Glycemic Control",
        "unit": "mg/dL",
        "ref": ReferenceInterval(low=70.0, high=99.0),
        "regex": r"(?:fasting\s*(?:blood\s*)?glucose|glucose\s*fasting)[^\d\n]*?(\d+(?:\.\d+)?)"
    },
    {
        "code": "FERRITIN",
        "loinc_code": "24331-1",
        "display_name": "Serum Ferritin (Iron Reserve)",
        "category": "Iron Panel",
        "unit": "ng/mL",
        "ref": ReferenceInterval(low=30.0, high=200.0),
        "regex": r"(?:ferritin|serum\s*ferritin)[^\d\n]*?(\d+(?:\.\d+)?)"
    },
    {
        "code": "HS_CRP",
        "loinc_code": "30934-4",
        "display_name": "High-Sensitivity CRP",
        "category": "Inflammation",
        "unit": "mg/L",
        "ref": ReferenceInterval(low=0.0, high=1.0),
        "regex": r"(?:hs-?crp|high\s*sensitivity\s*c-?reactive\s*protein|crp\s*high\s*sensitivity)[^\d\n]*?(\d+(?:\.\d+)?)"
    },
    {
        "code": "VITAMIN_D3",
        "loinc_code": "62292-8",
        "display_name": "Vitamin D (25-OH)",
        "category": "Vitamins",
        "unit": "ng/mL",
        "ref": ReferenceInterval(low=30.0, high=100.0),
        "regex": r"(?:vitamin\s*d|25-?hydroxy\s*vitamin\s*d)[^\d\n]*?(\d+(?:\.\d+)?)"
    },
    {
        "code": "URIC_ACID",
        "loinc_code": "3084-1",
        "display_name": "Serum Uric Acid",
        "category": "Renal & Metabolic",
        "unit": "mg/dL",
        "ref": ReferenceInterval(low=3.5, high=7.0),
        "regex": r"(?:uric\s*acid|serum\s*urate)[^\d\n]*?(\d+(?:\.\d+)?)"
    }
]

class LabPdfParser:
    def extract_text(self, pdf_bytes: bytes) -> str:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
        return "\n".join(pages_text)

    def parse_biomarkers(self, text: str) -> List[BiomarkerObservation]:
        observations = []
        text_lower = text.lower()

        for pattern in BIOMARKER_PATTERNS:
            match = re.search(pattern["regex"], text_lower, re.IGNORECASE)
            if match:
                try:
                    val = float(match.group(1))
                    status = evaluate_status(pattern["code"], val)
                    obs = BiomarkerObservation(
                        code=pattern["code"],
                        loinc_code=pattern["loinc_code"],
                        display_name=pattern["display_name"],
                        category=pattern["category"],
                        numeric_value=val,
                        unit=pattern["unit"],
                        reference_interval=pattern["ref"],
                        status=status
                    )
                    observations.append(obs)
                except (ValueError, IndexError):
                    continue

        return observations

pdf_parser = LabPdfParser()
