import pytest
from app.services.pdf_parser import pdf_parser

def test_pdf_text_biomarker_extraction():
    sample_lab_report_text = """
    QUEST DIAGNOSTICS LABORATORY REPORT
    PATIENT: DEMO, ALEX    DOB: 1990-05-12
    TEST REQUESTED                     RESULT    REFERENCE RANGE    UNITS
    ---------------------------------------------------------------------
    Apolipoprotein B                   118       50-90              mg/dL (HIGH)
    LDL Cholesterol                    142       <100               mg/dL (HIGH)
    Hemoglobin A1c                     5.8       4.0-5.6            %     (HIGH)
    Serum Ferritin                     18        30-200             ng/mL (LOW)
    High Sensitivity C-Reactive Prot   2.8       <1.0               mg/L  (HIGH)
    """

    observations = pdf_parser.parse_biomarkers(sample_lab_report_text)
    assert len(observations) >= 4

    obs_map = {o.code: o for o in observations}
    assert "APOB" in obs_map
    assert obs_map["APOB"].numeric_value == 118.0
    assert obs_map["APOB"].status == "HIGH"

    assert "FERRITIN" in obs_map
    assert obs_map["FERRITIN"].numeric_value == 18.0
    assert obs_map["FERRITIN"].status == "LOW"

    assert "HBA1C" in obs_map
    assert obs_map["HBA1C"].numeric_value == 5.8
