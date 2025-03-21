from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, relationship, validates
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
import uuid
import re

# Create database engine - properly escape special characters in password
password = quote_plus("Abc123456")  # URL encode the password
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://admin:{password}@database-video.c1siqkqs2a46.ap-southeast-2.rds.amazonaws.com:3306/db_sub_video"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define a function to get the current time in UTC +7
def utc_plus_7():
    return datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=7)
# Create Base class
Base = declarative_base()

class User(Base):
    __tablename__ = "user"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # This will store hashed password
    email = Column(String(100), unique=True, nullable=False)
    
    # Relationship with videos
    videos = relationship("Video", back_populates="user")

    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        return email

class Video(Base):
    __tablename__ = "videos"

    video_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("user.user_id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)
    
    # Relationship with user
    user = relationship("User", back_populates="videos")
    
    # Relationships with SRT, VIDEO_TTS, and VIDEO_SUB
    srt = relationship("SRT", back_populates="video")
    video_tts = relationship("VIDEO_TTS", back_populates="video")
    video_sub = relationship("VIDEO_SUB", back_populates="video")

class SRT(Base):
    __tablename__ = "srt"
    
    srt_id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.video_id"), nullable=False)
    srt_name = Column(String(255), nullable=False)
    srt_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Relationship with video
    video = relationship("Video", back_populates="srt")
    
    # Relationship with VIDEO_TTS and VIDEO_SUB
    video_tts = relationship("VIDEO_TTS", back_populates="srt")
    video_sub = relationship("VIDEO_SUB", back_populates="srt")

class VIDEO_TTS(Base):
    __tablename__ = "video_tts"

    video_tts_id = Column(Integer, primary_key=True, autoincrement=True)
    srt_id = Column(Integer, ForeignKey("srt.srt_id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.video_id"), nullable=False)  # Fix lỗi thiếu Foreign Key
    video_tts_name = Column(String(255), nullable=False)
    video_tts_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Relationship with SRT
    srt = relationship("SRT", back_populates="video_tts")
    # Relationship with Video
    video = relationship("Video", back_populates="video_tts")

class VIDEO_SUB(Base):
    __tablename__ = "video_sub"

    video_sub_id = Column(Integer, primary_key=True, autoincrement=True)
    srt_id = Column(Integer, ForeignKey("srt.srt_id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.video_id"), nullable=False)  # Fix lỗi thiếu Foreign Key
    video_sub_name = Column(String(255), nullable=False)
    video_sub_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Relationship with SRT
    srt = relationship("SRT", back_populates="video_sub")
    # Relationship with Video
    video = relationship("Video", back_populates="video_sub")

class BlackListToken(Base):
    __tablename__ = "black_list_token"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invalid_token = Column(String(255), nullable=False, unique=True)  # Format: BLACK_LIST_{uid}_{jit}
    created_at = Column(DateTime, default=utc_plus_7) # Format (UTC): YYYY-MM-DD HH:MM:SS

# Create all tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
