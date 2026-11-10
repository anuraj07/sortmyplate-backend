import pytest
from app.core.crypto import fle_service

def test_field_level_encryption_string():
    sensitive_data = "Patient LDL=145mg/dL, Ferritin=18ng/mL"
    ciphertext = fle_service.encrypt_string(sensitive_data)
    
    assert ciphertext != sensitive_data
    assert len(ciphertext) > 20
    
    decrypted = fle_service.decrypt_string(ciphertext)
    assert decrypted == sensitive_data

def test_field_level_encryption_json():
    observations = {
        "HBA1C": {"value": 5.8, "unit": "%", "status": "HIGH"},
        "FERRITIN": {"value": 18.0, "unit": "ng/mL", "status": "LOW"}
    }
    encrypted = fle_service.encrypt_json(observations)
    assert "HBA1C" not in encrypted
    
    decrypted = fle_service.decrypt_json(encrypted)
    assert decrypted["HBA1C"]["value"] == 5.8
    assert decrypted["FERRITIN"]["status"] == "LOW"
