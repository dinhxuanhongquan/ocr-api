from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.api import deps
from app.models.user import User
from app.models.video import Video
from app.schemas.video import Video as VideoSchema, VideoCreate
from app.services.s3 import s3_service
from app.db.session import get_db
import uuid

router = APIRouter()

@router.post("/upload", response_model=VideoSchema)
async def upload_video(
    *,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Upload a new video.
    """
    # Generate unique filename
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    s3_key = f"videos/{current_user.id}/{unique_filename}"
    
    # Upload to S3
    await s3_service.upload_file(file.file, s3_key)
    
    # Create video record in database
    video = Video(
        name=file.filename,
        user_id=current_user.id,
        s3_key=s3_key,
        status="pending"
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video

@router.get("/", response_model=List[VideoSchema])
def get_videos(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get all videos for the current user.
    """
    return db.query(Video).filter(Video.user_id == current_user.id).all()

@router.get("/{video_id}", response_model=VideoSchema)
def get_video(
    *,
    db: Session = Depends(get_db),
    video_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific video by ID.
    """
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.delete("/{video_id}")
def delete_video(
    *,
    db: Session = Depends(get_db),
    video_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a video.
    """
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete from S3
    await s3_service.delete_file(video.s3_key)
    
    # Delete from database
    db.delete(video)
    db.commit()
    return {"message": "Video deleted successfully"} 