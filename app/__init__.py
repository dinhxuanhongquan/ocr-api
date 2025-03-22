from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os

def create_app() -> FastAPI:
    app = FastAPI(
        title="Video Translation API",
        description="API for video translation and OCR services",
        version="1.0.0"
    )

    # Add SessionMiddleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv('SESSION_SECRET_KEY', 'your-secret-key-here'),
        session_cookie="session"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and include routers
    from app.api.v1 import auth, videos
    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
    app.include_router(videos.router, prefix="/api/v1", tags=["videos"])

    return app 