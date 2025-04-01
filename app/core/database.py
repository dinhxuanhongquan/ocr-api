from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from app.models.user import User
from app.models.video import Video, SRT, VIDEO_TTS
# Tạo bảng nếu chưa tồn tại - đặt ở cuối file sau khi import models
Base.metadata.create_all(bind=engine, checkfirst=True)

