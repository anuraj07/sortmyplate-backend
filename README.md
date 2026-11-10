# SortMyPlate Backend (FastAPI & Zero-Trust PHI Vault)

> **AI-Driven, Zero-Trust Biomarker Nutrition Engine for Individuals, Families & Flatmates**

SortMyPlate ingests semi-annual or annual full-body blood biomarker panels, encrypts clinical observations using AES-256-GCM Field-Level Encryption, and powers instant, explainable "Next Meal" recommendations across any client interface.

---

## Key Architecture Features

- **Zero-Trust PHI Vault**: Decouples user identity from clinical data via synthetic `subject_token`s and application-level **AES-256-GCM Field-Level Encryption**.
- **Google OAuth2 Sign-In**: Individual profiles with 1-click demo authentication (`alex.demo@gmail.com`).
- **Dynamic Households & Circles**: Join/leave groups and dynamically toggle who is eating right now on every "Next Meal" click.
- **Multi-Stage Clinical Consensus**: Hard allergy elimination + "Shared Base, Custom Finish" recipe matching + biochemical mechanisms.
- **Model-Agnostic LLM Gateway**: Supports DeepSeek-V3, Anthropic Claude 3.5, OpenAI GPT-4o, local Ollama, and built-in deterministic fallback.
- **SQLAlchemy 2.0 Async**: Zero-setup local SQLite (`aiosqlite`), ready to switch to PostgreSQL 16+ (`asyncpg`) via `.env`.

---

## Quickstart

### 1. Local Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
- **Web Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Run Tests & Demo
```bash
pytest tests/
python3 demo.py
```

### 3. Deploy to Cloud (RamNaym Cloud / PaaS)
Run `./package_deploy.sh` to generate a clean deployment ZIP, or push directly to GitHub.
