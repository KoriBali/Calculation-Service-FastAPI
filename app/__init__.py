from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import Config
import os
from datetime import datetime, timezone
from app.shared.errors import register_error_handlers


def create_app():
    # redirect_slashes=False: "/health/" is 404 like Flask, not a 307 redirect.
    app = FastAPI(
        title="Kori Bali Calculation Service",
        version="1.0.0",
        debug=Config.DEBUG,
        redirect_slashes=False,
    )

    # Echo the request Origin like flask-cors CORS(app) instead of sending "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    API_KEY = os.getenv("SECRET_KEY", "secret_cadangan")

    # Security with SECRET_KEY PENTING JANGAN DI HAPUS
    # @app.middleware("http")
    # async def validate_api_key(request: Request, call_next):
    #     incoming_key = request.headers.get("X-Internal-Key")
    #     print(incoming_key)

    #     if incoming_key != API_KEY:
    #         return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    #     return await call_next(request)

    # ganti "*" di allow_origins dengan URL Railway API Gateway
    # app.add_middleware(CORSMiddleware, allow_origins=["*"])


    """Entry Point Start"""
    @app.get("/")
    def root():
        return {
            "name": "Kori Bali Calculation Service",
            "status": "online",
            "version": "1.0.0",
            "server_time": datetime.now(timezone.utc).isoformat()
        }

    @app.get("/health")
    def health():
        return {
            "status": "healthy"
        }

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException):
        if error.status_code == 404:
            return JSONResponse({
                "error": "Route not found",
                "path": request.url.path
            }, status_code=404)
        return JSONResponse(
            {"detail": error.detail},
            status_code=error.status_code,
            headers=getattr(error, "headers", None),
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception):
        return JSONResponse({
            "error": "Internal server error"
        }, status_code=500)
    """Entry Point End"""

    register_error_handlers(app)

    # Register Routers

    # add the import here
    from app.pole.routes import pole_router

    # add the router here
    app.include_router(pole_router)


    return app
