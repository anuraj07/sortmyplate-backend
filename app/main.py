import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
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
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = (request.headers.get("x-forwarded-proto") or "").lower()
        if forwarded_host:
            host = forwarded_host.split(",")[0].strip()
            scheme = "https" if ("https" in forwarded_proto or "ramnaymcloud.com" in host) else request.url.scheme
            base_url = f"{scheme}://{host}".rstrip("/")
        else:
            base_url = str(request.base_url).rstrip("/")
            if ("https" in forwarded_proto or "ramnaymcloud.com" in base_url) and base_url.startswith("http://"):
                base_url = base_url.replace("http://", "https://", 1)

        return {
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "base_url": base_url,
            "google_client_id": settings.GOOGLE_CLIENT_ID or None,
            "endpoints": {
                "health": "/health",
                "llm_status": "/health/llm-status",
                "auth_google": f"{settings.API_V1_STR}/auth/google",
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
