# SortMyPlate Backend (FastAPI & Zero-Trust PHI Vault)

> **AI-Driven, Zero-Trust Biomarker Nutrition Engine for Individuals, Families & Flatmates**

SortMyPlate ingests semi-annual or annual full-body blood biomarker panels, encrypts clinical observations using AES-256-GCM Field-Level Encryption, and powers instant, explainable "Next Meal" recommendations across any client interface.

**Production Base URL**: [https://j6tgemptpq36.ramnaymcloud.com](https://j6tgemptpq36.ramnaymcloud.com)

---

## Key Architecture Features

- **Dynamic Endpoint Discovery (`GET /bootstrap`)**: Clients make a single initial discovery call on startup to retrieve session API paths dynamically instead of hardcoding endpoints.
- **Zero-Trust PHI Vault**: Decouples user identity from clinical data via synthetic `subject_token`s and application-level **AES-256-GCM Field-Level Encryption**.
- **Google OAuth2 Sign-In**: Real user accounts via `/v1/auth/google` (optional `GOOGLE_CLIENT_ID` token verification; no pre-seeded demo users).
- **Dynamic Households & Circles**: Create groups, join via invite code, leave groups, and toggle who is eating right now on every "Next Meal" click.
- **Multi-Stage Clinical Consensus**: Hard allergy elimination + "Shared Base, Custom Finish" recipe matching + biochemical mechanisms.
- **Model-Agnostic LLM Gateway**: Supports DeepSeek-V3, Anthropic Claude 3.5, OpenAI GPT-4o, and built-in deterministic clinical fallback.
- **SQLAlchemy 2.0 Async**: Zero-setup SQLite (`aiosqlite`), ready to switch to PostgreSQL 16+ (`asyncpg`) via `.env`.

---

## Production & Local Endpoints

- **Web Dashboard**: [https://j6tgemptpq36.ramnaymcloud.com/](https://j6tgemptpq36.ramnaymcloud.com/)
- **Discovery Endpoint**: [https://j6tgemptpq36.ramnaymcloud.com/bootstrap](https://j6tgemptpq36.ramnaymcloud.com/bootstrap)
- **Health Check**: [https://j6tgemptpq36.ramnaymcloud.com/health](https://j6tgemptpq36.ramnaymcloud.com/health)
- **Swagger API Docs**: [https://j6tgemptpq36.ramnaymcloud.com/docs](https://j6tgemptpq36.ramnaymcloud.com/docs)

---

## Quickstart

### 1. Local Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Run Tests & Demo
```bash
.venv/bin/pytest tests/
.venv/bin/python3 demo.py
```

### 3. Deploy to Cloud (RamNaym Cloud / PaaS)
Run `./package_deploy.sh` to generate a clean deployment ZIP (`sortmyplate-backend-deploy.zip`), or connect the backend GitHub repository directly.
