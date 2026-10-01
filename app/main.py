import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.router import router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, request_id_context
from app.db.session import make_engine, make_sessions

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, engine: AsyncEngine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        config = settings or get_settings()
        configure_logging(config.log_level)
        database = engine or make_engine(config)
        application.state.settings = config
        application.state.sessions = make_sessions(database)
        try:
            yield
        finally:
            if engine is None:
                await database.dispose()

    application = FastAPI(
        title="ShetiSevek AI", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid4())
        token = request_id_context.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        finally:
            request_id_context.reset(token)

    @application.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code,
                "request_id": request.state.request_id,
            },
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("database_error")
        return JSONResponse(
            status_code=503,
            content={
                "error": "database_unavailable",
                "request_id": request.state.request_id,
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_request",
                "request_id": request.state.request_id,
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unexpected_error")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    application.include_router(router)
    return application


app = create_app()
