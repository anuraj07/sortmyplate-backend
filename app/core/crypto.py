import os
import base64
import json
from typing import Any, Dict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

class FieldLevelEncryption:
    """
    Application-level Field-Level Encryption (FLE) using AES-256-GCM.
    Ensures Protected Health Information (PHI) like blood biomarker readings
    are stored encrypted at rest in the database.
    """
    def __init__(self, key: bytes = None):
        if key:
            self._key = key
        else:
            # Derive 256-bit key from secret key
            raw = settings.SECRET_KEY.encode("utf-8")
            if len(raw) < 32:
                raw = raw.ljust(32, b"0")
            self._key = raw[:32]
        self._aesgcm = AESGCM(self._key)

    def encrypt_string(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        # 96-bit nonce for GCM
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Store as base64: nonce + ciphertext (which includes 16-byte tag)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")

    def decrypt_string(self, ciphertext_b64: str) -> str:
        if not ciphertext_b64:
            return ""
        raw = base64.b64decode(ciphertext_b64.encode("utf-8"))
        nonce = raw[:12]
        ciphertext = raw[12:]
        plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")

    def encrypt_json(self, data: Dict[str, Any]) -> str:
        json_str = json.dumps(data)
        return self.encrypt_string(json_str)

    def decrypt_json(self, ciphertext_b64: str) -> Dict[str, Any]:
        json_str = self.decrypt_string(ciphertext_b64)
        return json.loads(json_str)

fle_service = FieldLevelEncryption()
