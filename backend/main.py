"""
FabricShield AI — FastAPI Application Entry Point
Production-ready ASGI app with structured logging, telemetry, and CORS.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from opencensus.ext.azure.log_exporter import AzureLogHandler

from backend.api import approvals, audit, connections, powerbi, scan
from backend.config import get_settings
from backend.marketplace.fulfillment import marketplace_router
from backend.governance.purview import purview_router

settings = get_settings()

# ─── Structured Logging ───────────────────────────────────────────────────────

def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Azure Application Insights handler
    if settings.applicationinsights_connection_string:
        ai_handler = AzureLogHandler(
            connection_string=settings.applicationinsights_connection_string
        )
        root_logger.addHandler(ai_handler)


setup_logging()
logger = structlog.get_logger(__name__)


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "fabricshield.startup",
        version=settings.app_version,
        environment=settings.environment,
    )
    yield
    logger.info("fabricshield.shutdown")


# ─── App Factory ─────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Enterprise PII/PHI Governance Platform for Azure SQL & Microsoft Fabric",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── Security Middleware ───────────────────────────────────────────────────
    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.azurewebsites.net", "*.fabricshield.io", "localhost"],
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    # ── Request Tracing Middleware ────────────────────────────────────────────
    @app.middleware("http")
    async def request_tracing(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.monotonic()

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            logger.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown",
            )

            try:
                response: Response = await call_next(request)
            except Exception as exc:
                logger.exception("http.unhandled_error", error=str(exc))
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error", "request_id": request_id},
                )

            duration_ms = round((time.monotonic() - start) * 1000, 2)
            logger.info(
                "http.response",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            return response

    # ── Security Headers Middleware ───────────────────────────────────────────
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self' https://login.microsoftonline.com https://api.powerbi.com; "
            "frame-src https://app.powerbi.com; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com"
        )
        return response

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(scan.router, prefix="/api/v1", tags=["Scan"])
    app.include_router(connections.router, prefix="/api/v1", tags=["Connections"])
    app.include_router(approvals.router, prefix="/api/v1", tags=["Approvals"])
    app.include_router(audit.router, prefix="/api/v1", tags=["Audit"])
    app.include_router(powerbi.router, prefix="/api/v1", tags=["PowerBI"])
    app.include_router(marketplace_router, prefix="/marketplace", tags=["Marketplace"])
    app.include_router(purview_router, prefix="/api/v1", tags=["Governance"])

    # ── Health Check ──────────────────────────────────────────────────────────
    @app.get("/health", include_in_schema=False)
    async def health_check():
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
        }

    @app.get("/api/v1/ping", include_in_schema=False)
    async def ping():
        return {"pong": True}

    return app


app = create_app()
