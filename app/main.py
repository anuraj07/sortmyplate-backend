import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.db.seed import init_db_and_seed
from app.api.v1.auth import router as auth_router
from app.api.v1.groups import router as groups_router
from app.api.v1.biomarkers import router as biomarkers_router
from app.api.v1.meals import router as meals_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seed dummy user on startup
    await init_db_and_seed()
    yield

def create_application() -> FastAPI:
    app = FastAPI(
        title="SortMyPlate Core Headless API",
        description=(
            "AI-driven, zero-trust biomarker nutrition engine. "
            "Features AES-256-GCM Field-Level Encryption, Google Sign-In, "
            "dynamic household/flat circles, PDF lab ingestion, "
            "and instant explainable next-meal recommendations powered by DeepSeek/LLM."
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
