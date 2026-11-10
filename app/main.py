import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.security import resolve_public_base_url
from app.db.seed import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.groups import router as groups_router
from app.api.v1.biomarkers import router as biomarkers_router
from app.api.v1.meals import router as meals_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup (no demo user seeded)
    await init_db()
    yield

def create_application() -> FastAPI:
    app = FastAPI(
        title="SortMyPlate Core Headless API",
        description=(
            "AI-driven, zero-trust biomarker nutrition engine. "
            "Features AES-256-GCM Field-Level Encryption, Google Sign-In, "
            "dynamic endpoint discovery (/bootstrap), dynamic household/flat circles, "
            "PDF lab ingestion, and explainable next-meal recommendations."
        ),
        version=settings.VERSION,
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS configuration for multiple frontends (iOS, Android, Web, Smart displays)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_in_app_auth_headers(request: Request, call_next):
        response = await call_next(request)
        # Allow Google Identity Services One Tap / in-page credential modals cleanly
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
        return response

    # Mount API routers
    app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Google Authentication"])
    app.include_router(groups_router, prefix=f"{settings.API_V1_STR}/groups", tags=["Households & Circles"])
    app.include_router(biomarkers_router, prefix=f"{settings.API_V1_STR}/health/biomarkers", tags=["Biomarkers & Encrypted PHI Vault"])
    app.include_router(meals_router, prefix=f"{settings.API_V1_STR}/meals", tags=["Next Meal Engine"])

    # Mount static assets for frontend website
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", tags=["Frontend Website"])
    async def serve_index():
        index_file = os.path.join(static_dir, "index.html")
        return FileResponse(index_file)

    @app.get("/bootstrap", tags=["Endpoint Discovery"])
    def get_bootstrap_endpoints(request: Request):
        """
        Dynamic Service Discovery Endpoint.
        Frontends make their first call here on startup to obtain all API endpoint paths
        for the current session, avoiding hardcoded endpoint URLs.
        """
        base_url = resolve_public_base_url(request)
        google_client_id = settings.GOOGLE_CLIENT_ID.strip()
        google_client_secret = settings.GOOGLE_CLIENT_SECRET.strip()

        return {
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "base_url": base_url,
            "google_client_id": google_client_id or None,
            "google_oauth_enabled": bool(google_client_id and google_client_secret),
            "google_gis_enabled": bool(google_client_id),
            "endpoints": {
                "health": "/health",
                "llm_status": "/health/llm-status",
                "auth_google": f"{settings.API_V1_STR}/auth/google",
                "auth_google_login": f"{settings.API_V1_STR}/auth/google/login",
                "auth_google_exchange": f"{settings.API_V1_STR}/auth/google/exchange",
                "auth_google_session": f"{settings.API_V1_STR}/auth/google/session/{{oauth_state}}",
                "auth_me": f"{settings.API_V1_STR}/auth/me",
                "auth_profile": f"{settings.API_V1_STR}/auth/profile",
                "groups_create": f"{settings.API_V1_STR}/groups/create",
                "groups_join": f"{settings.API_V1_STR}/groups/join",
                "groups_leave": f"{settings.API_V1_STR}/groups/{{group_id}}/leave",
                "groups_my": f"{settings.API_V1_STR}/groups/my",
                "groups_members": f"{settings.API_V1_STR}/groups/{{group_id}}/members",
                "biomarkers_record": f"{settings.API_V1_STR}/health/biomarkers/record",
                "biomarkers_upload_pdf": f"{settings.API_V1_STR}/health/biomarkers/upload-pdf",
                "biomarkers_latest": f"{settings.API_V1_STR}/health/biomarkers/latest",
                "biomarkers_abnormals": f"{settings.API_V1_STR}/health/biomarkers/abnormals",
                "biomarkers_encryption_status": f"{settings.API_V1_STR}/health/biomarkers/encryption-status",
                "meals_next": f"{settings.API_V1_STR}/meals/next"
            }
        }

    @app.get("/health", tags=["System"])
    def health_check():
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "security": "AES-256-GCM Field-Level Encryption Active",
            "llm_provider": settings.LLM_PROVIDER
        }

    @app.get("/health/llm-status", tags=["System"])
    async def llm_status():
        """
        Tests and returns real-time connectivity to the configured LLM model.
        """
        from app.services.llm.factory import check_llm_connectivity
        return await check_llm_connectivity()

    return app

app = create_application()
