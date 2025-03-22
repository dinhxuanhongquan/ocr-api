from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, relationship, validates, declarative_base
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
import uuid
import re

# Cấu hình Database URL (encode mật khẩu)
password = quote_plus("Abc123456")
endpoint = "database-video.c1siqkqs2a46.ap-southeast-2.rds.amazonaws.com"
port = "3306"
database = "db_sub_video"
user = "admin"
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{user}:{password}@{endpoint}:{port}/{database}"

#  Kết nối Database
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_recycle=3600)

#  Tạo session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#  Base Model
Base = declarative_base()

#  Hàm lấy thời gian UTC+7
def utc_plus_7():
    return datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=7)

#  Model User
class User(Base):
    __tablename__ = "user"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # Mật khẩu đã hash
    email = Column(String(100), unique=True, nullable=False)

    # Quan hệ với Video
    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)

    #  Validate email
    @validates("email")
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        return email

#  Model Video
class Video(Base):
    __tablename__ = "videos"

    video_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Quan hệ với User
    user = relationship("User", back_populates="videos")

    # Quan hệ với SRT, VIDEO_TTS, VIDEO_SUB
    srt = relationship("SRT", back_populates="video", cascade="all, delete-orphan", passive_deletes=True)
    video_tts = relationship("VIDEO_TTS", back_populates="video", cascade="all, delete-orphan", passive_deletes=True)
    video_sub = relationship("VIDEO_SUB", back_populates="video", cascade="all, delete-orphan", passive_deletes=True)

#  Model SRT
class SRT(Base):
    __tablename__ = "srt"
    
    srt_id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    srt_name = Column(String(255), nullable=False)
    srt_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Quan hệ với Video
    video = relationship("Video", back_populates="srt")

    # Quan hệ với VIDEO_TTS và VIDEO_SUB
    video_tts = relationship("VIDEO_TTS", back_populates="srt", cascade="all, delete-orphan", passive_deletes=True)
    video_sub = relationship("VIDEO_SUB", back_populates="srt", cascade="all, delete-orphan", passive_deletes=True)

#  Model VIDEO_TTS
class VIDEO_TTS(Base):
    __tablename__ = "video_tts"

    video_tts_id = Column(Integer, primary_key=True, autoincrement=True)
    srt_id = Column(Integer, ForeignKey("srt.srt_id", ondelete="CASCADE"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    video_tts_name = Column(String(255), nullable=False)
    video_tts_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Quan hệ với SRT và Video
    srt = relationship("SRT", back_populates="video_tts")
    video = relationship("Video", back_populates="video_tts")

#  Model VIDEO_SUB
class VIDEO_SUB(Base):
    __tablename__ = "video_sub"

    video_sub_id = Column(Integer, primary_key=True, autoincrement=True)
    srt_id = Column(Integer, ForeignKey("srt.srt_id", ondelete="CASCADE"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    video_sub_name = Column(String(255), nullable=False)
    video_sub_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Quan hệ với SRT và Video
    srt = relationship("SRT", back_populates="video_sub")
    video = relationship("Video", back_populates="video_sub")

#  Model BlackListToken
class BlackListToken(Base):
    __tablename__ = "black_list_token"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invalid_token = Column(String(255), nullable=False, unique=True)  # BLACK_LIST_{uid}_{jit}
    created_at = Column(DateTime, default=utc_plus_7)

#  Tạo bảng nếu chưa tồn tại
Base.metadata.create_all(bind=engine, checkfirst=True)

#  Dependency cho FastAPI hoặc SQLAlchemy Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
