import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_llm_status_endpoint():
    with TestClient(app) as client:
        res = client.get("/health/llm-status")
        assert res.status_code == 200
        data = res.json()
        assert "provider" in data
        assert "status" in data
        # Default in test environment is "mock"
        assert data["provider"] == "mock"
        assert data["status"] == "ONLINE"
