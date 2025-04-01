from sqlalchemy.orm import Session
from app.models.video import Video, SRT, VIDEO_TTS
from app.schemas.video import VideoUpdate, SRTCreate, SRTUpdate, VideoTTSCreate, VideoTTSUpdate, VideoTTS
from fastapi import HTTPException, status
from typing import List, Optional
from app.core.config import get_settings
import boto3
import os

settings = get_settings()
# Cau hinh S3
s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION
)

def get_video(
        db: Session, 
        video_id: str
        ):
    return db.query(Video).filter(Video.video_id == video_id).first()

def get_all_relationship_with_video(
        db: Session,
        video_id: str
        ):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    srt = db.query(SRT).filter(SRT.video_id == video_id).first()
    video_tts = db.query(VIDEO_TTS).filter(VIDEO_TTS.video_id == video_id).first()
    return video, srt, video_tts

def get_user_videos(
        db: Session, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100):
    return db.query(Video).filter(Video.user_id == user_id).offset(skip).limit(limit).all()

def create_video(
        db: Session, 
        video: VideoUpdate, 
        user_id: str):
    db_video = Video(**video.dict(), user_id=user_id)
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

def delete_video(
        db: Session, 
        video_id: str
        ):
    db_video = get_video(db, video_id)
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    db.delete(db_video)
    db.commit()
    return {"message": "Video deleted successfully"}

def update_video(
        db: Session, 
        video_id: str,
        video: VideoUpdate
        ):
    db_video = db.query(Video).filter(Video.video_id == video_id).first()
    if not db_video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Video not found")
    
    old_video_name = db_video.file_name
    old_video_url = db_video.file_url

    # update video_name if it is not None
    if video.file_name is not None:
        db_video.file_name = video.file_name
    else:
        db_video.file_name = old_video_name
    # update video_url if it is not None
    if video.file_url is not None:
        db_video.file_url = video.file_url
    else:
        db_video.file_url = old_video_url
    db.commit()
    db.refresh(db_video)
    return db_video

def create_srt(
        db: Session, 
        srt: SRTCreate
        ) -> SRT:
    db_srt = SRT(
        srt_name = srt.srt_name,
        srt_url = srt.srt_url,
        srt_url_sub = srt.srt_url_sub,
        video_id = srt.video_id
    )
    db.add(db_srt)
    db.commit()
    db.refresh(db_srt)
    return db_srt

def get_srt_by_video_id(
        db: Session, 
        video_id: str
        ):
    return db.query(SRT).filter(SRT.video_id == video_id).all()

def get_srt_by_srt_id(
        db: Session, 
        video_id: str, 
        srt_id: str
        ):
    return db.query(SRT).filter(SRT.video_id == video_id, SRT.srt_id == srt_id).first()

def delete_srt(
        db: Session, 
        srt_id: str
        ):
    db_srt = db.query(SRT).filter(SRT.srt_id == srt_id).first()
    if not db_srt:
        raise HTTPException(status_code=404, detail="SRT not found")
    
    db.delete(db_srt)
    db.commit()
    return {"message": "SRT deleted successfully"}

def update_srt(
        db: Session, 
        srt_id: str,
        srt: SRTUpdate
        ):
    db_srt = db.query(SRT).filter(SRT.srt_id == srt_id).first()
    if not db_srt:
        raise HTTPException(status_code=404, detail="SRT not found")
    
    old_srt_name = db_srt.srt_name
    old_srt_url = db_srt.srt_url
    old_srt_url_sub = db_srt.srt_url_sub

    # update srt_name if it is not None
    if srt.srt_name is not None:
        db_srt.srt_name = srt.srt_name
    else:
        db_srt.srt_name = old_srt_name
    # update srt_url if it is not None
    if srt.srt_url is not None:
        db_srt.srt_url = srt.srt_url
    else:
        db_srt.srt_url = old_srt_url
    # update srt_url_sub if it is not None
    if srt.srt_url_sub is not None:
        db_srt.srt_url_sub = srt.srt_url_sub
    else:
        db_srt.srt_url_sub = old_srt_url_sub
    db.commit()
    db.refresh(db_srt)
    return db_srt

def create_video_tts(
        db: Session, 
        video_tts: VideoTTS
        ):
    db_video_tts = VIDEO_TTS(**video_tts.dict())
    db.add(db_video_tts)
    db.commit()
    db.refresh(db_video_tts)
    return db_video_tts

def get_video_tts(
        db: Session, 
        video_id: str
        ):
    return db.query(VIDEO_TTS).filter(VIDEO_TTS.video_id == video_id).first()

def get_video_tts_by_id(
        db: Session, 
        video_tts_id: str
        ):
    return db.query(VIDEO_TTS).filter(VIDEO_TTS.video_tts_id == video_tts_id).first()