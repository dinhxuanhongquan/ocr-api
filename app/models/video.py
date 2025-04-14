from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.config import utc_plus_7
import uuid

#  Model Video
class Video(Base):
    __tablename__ = "videos"

    video_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Quan hệ với User
    user = relationship("User", back_populates="videos")

    # Quan hệ với SRT, VIDEO_TTS, VIDEO_SUB
    srt = relationship("SRT", back_populates="video", cascade="all, delete-orphan", passive_deletes=True)
    video_tts = relationship("VIDEO_TTS", back_populates="video", cascade="all, delete-orphan", passive_deletes=True)
    # video_sub = relationship("VIDEO_SUB", back_populates="video", cascade="all, delete-orphan", passive_deletes=True)

#  Model SRT
class SRT(Base):
    __tablename__ = "srt"
    
    srt_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    srt_name = Column(String(255), nullable=False)
    srt_url = Column(String(500), nullable=False)
    srt_url_sub = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Quan hệ với Video
    video = relationship("Video", back_populates="srt")

    # Quan hệ với VIDEO_TTS và VIDEO_SUB
    video_tts = relationship("VIDEO_TTS", back_populates="srt", cascade="all, delete-orphan", passive_deletes=True)
    # video_sub = relationship("VIDEO_SUB", back_populates="srt", cascade="all, delete-orphan", passive_deletes=True)

#  Model VIDEO_TTS
class VIDEO_TTS(Base):
    __tablename__ = "video_tts"

    video_tts_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    srt_id = Column(String(36), ForeignKey("srt.srt_id", ondelete="CASCADE"), nullable=False)
    video_id = Column(String(36), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False)
    video_tts_name = Column(String(255), nullable=False)
    video_tts_url = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_plus_7)

    # Quan hệ với SRT và Video
    srt = relationship("SRT", back_populates="video_tts")
    video = relationship("Video", back_populates="video_tts")
