from pydantic_settings import BaseSettings
from functools import lru_cache
from urllib.parse import quote_plus
from datetime import datetime, timedelta, timezone
import re
import os

class Settings(BaseSettings):
    app_name: str = "Video OCR"
    app_version: str = "1.0.0"
    # Database settings
    DATABASE_URL: str = "mysql+pymysql://username:password@databasename.c1siqkqs2a46.ap-southeast-2.rds.amazonaws.com:3306/databasename"
    
    # JWT settings
    SECRET_KEY: str = "a_very_secret_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 300
    
    # AWS settings
    AWS_ACCESS_KEY_ID: str = "a_access_key_id"
    AWS_SECRET_ACCESS_KEY: str = "a_very_secret_key"
    AWS_BUCKET_INPUT_VIDEO: str = "video-input-storge"
    AWS_BUCKET_VIDEO_SUB: str = "video-sub"
    AWS_BUCKET_INPUT_SRT: str = "srt-input-storage"
    AWS_BUCKET_TEST: str = "video-translation-storage-bucket"
    AWS_REGION: str = "ap-southeast-2"
    
    # OAuth settings
    GOOGLE_CLIENT_ID: str = "your_client_id.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "your_client_secret"
    MICROSOFT_CLIENT_ID: str = "your_microsoft_client_id"
    MICROSOFT_CLIENT_SECRET: str = "your_microsoft_client_secret"

    # AI settings
    API_KEY: str = "your_api_key"
    API_MODEL: str = "your_api_model"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings() 

def utc_plus_7():
    return datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=7)

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be Windows-friendly"""
    if not filename:
        return ""
    # Extract name and extension
    name, ext = os.path.splitext(filename)
    
    # Remove invalid characters
    name = re.sub(r'[<>:"/\\|?*,]', '_', name)
    # Replace spaces with underscore
    name = name.replace(' ', '_')
    # Replace multiple underscores with single one
    name = re.sub(r'_+', '_', name)
    
    # Limit filename length to avoid path length issues
    if len(name) > 200:
        name = name[:200]
        
    return f"{name}{ext}"