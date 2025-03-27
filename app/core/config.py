from pydantic_settings import BaseSettings
from functools import lru_cache
from datetime import datetime, timedelta, timezone
import re
import os

class Settings(BaseSettings):
    app_name: str = "Video OCR"
    app_version: str = "1.0.0"
    # Database settings
    DATABASE_URL: str = "mysql+pymysql://admin:Abc123456@database-1.c1siqkqs2a46.ap-southeast-2.rds.amazonaws.com:3306/db_sub_video"
    
    # JWT settings
    SECRET_KEY: str = "/EyY1GnelIliNbL0Lempu5rEAzVZ5xQ4GWvO1dOTml0ouAA7EAmM5c84BoZPYlFi"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 300
    
    # AWS settings
    AWS_ACCESS_KEY_ID: str = "AKIAW5WU5HNSQ4BPJH6H"
    AWS_SECRET_ACCESS_KEY: str = "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"
    AWS_BUCKET_INPUT_VIDEO: str = "video-storge-bucket"
    AWS_BUCKET_VIDEO_SUB: str = "video-ub"
    AWS_BUCKET_INPUT_SRT: str = "srt-input-storage"
    AWS_BUCKET_TEST: str = "video-translation-storage-bucket"
    AWS_REGION: str = "ap-southeast-2"
    
    # OAuth settings
    GOOGLE_CLIENT_ID: str = "1024845742870-f5uj7qbrcqgnikipbd7u3j5rsmkfph4n.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "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"
    MICROSOFT_CLIENT_ID: str = "8c3e9e1f-836d-431a-a752-04af67b80154"
    MICROSOFT_CLIENT_SECRET: str = "0aa16d8a-a396-4e21-aa14-2a68a45786bc"
    
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