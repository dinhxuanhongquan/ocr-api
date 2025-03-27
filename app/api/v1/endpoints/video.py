from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.video import Video, SRT, VIDEO_TTS
from app.schemas.video import (
    VideoUpdate, Video as VideoSchema, 
    SRTCreate, SRTUpdate, SRT as SRTSchema, 
    VideoTTSCreate, VideoTTS as VideoTTSSchema
    )
from app.service import video_service
from app.core.config import get_settings
from app.core.config import sanitize_filename
import boto3
import os
import shutil
from pathlib import Path


settings = get_settings()
router = APIRouter()

# Cau hinh S3
s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION
)

# Contact with video
# pass
@router.post("/upload", response_model=None)
async def upload_video(
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra định dạng file
    if not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    os.makedirs("tempvideo", exist_ok=True)

    video_tmp = f"tempvideo/{video.filename}"
    
    try:
        with open(video_tmp, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        # Tạo tên file duy nhất
        unique_videoname = f"0_{video.filename}"
        count = 1
        
        while db.query(Video).filter(Video.file_name == unique_videoname).first():
            unique_videoname = f"{count}_{video.filename}"
            count += 1
        
        # Upload lên S3 (testing api)
        s3.upload_file(video_tmp, settings.AWS_BUCKET_TEST, unique_videoname)
        file_url = f"https://{settings.AWS_BUCKET_TEST}.s3.amazonaws.com/{unique_videoname}"
        
        # Lưu thông tin video vào database
        return video_service.create_video(db, VideoUpdate(file_name=unique_videoname, file_url=file_url), current_user.user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        # xoa file trong temp sau tho duoc tai len
        if os.path.exists(video_tmp):
            os.remove(video_tmp)

# pass
@router.get("/", response_model=list[VideoSchema])
async def get_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return video_service.get_user_videos(db, current_user.user_id, skip, limit)
    
# pass
@router.get("/{video_id}")
async def get_video_by_id(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    if not video_db:
        raise HTTPException(
            status_code=404, 
            detail="Video not found"
            )
    if current_user.user_id != video_db.user_id:
        raise HTTPException(
            status_code=403,
            detail="User not authorized to access this video"
        )
    return video_service.get_video(db, video_id)

# pass
@router.get("/relas/{video_id}")
async def get_all_relationship_with_video(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    if not video_db:
        raise HTTPException(
            status_code=404, 
            detail="Video not found"
            )
    if current_user.user_id != video_db.user_id:
        raise HTTPException(
            status_code=403,
            detail="User not authorized to access this video"
        )
    return video_service.get_all_relationship_with_video(db, video_id)

# pass
@router.put("/{video_id}", response_model=None)
async def update_video_by_id(
    video_id: str,
    video_update: VideoUpdate,  # Renamed parameter to avoid conflict
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get existing video
    db_video = db.query(Video).filter( Video.video_id == video_id).first()
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if user is authorized to update video
    if current_user.user_id != db_video.user_id:
        raise HTTPException(
            status_code=403,
            detail="User not authorized to update this video"
        )
    # Only proceed with S3 operations if filename has changed
    if video_update.file_name and video_update.file_name != db_video.file_name:
        try:
            # Copy to new name
            s3.copy_object(
                Bucket=settings.AWS_BUCKET_TEST,
                CopySource=f"{settings.AWS_BUCKET_TEST}/{db_video.file_name}",
                Key=video_update.file_name
            )
            # Delete old file
            s3.delete_object(
                Bucket=settings.AWS_BUCKET_TEST,
                Key=db_video.file_name
            )
            # Update URL
            video_update.file_url = f"https://{settings.AWS_BUCKET_TEST}.s3.amazonaws.com/{video_update.file_name}"
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update file in S3: {str(e)}"
            )

    return video_service.update_video(db, video_id, video_update)
# pass
@router.delete("/{video_id}", response_model=None)
async def delete_video_by_id(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # xoa video tren s3
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    s3.delete_object(Bucket=settings.AWS_BUCKET_TEST, Key=video.file_name)
    return video_service.delete_video(db, video_id)


# Contact with SRT
# pass
@router.post("/srt/upload/{video_id}", response_model=SRTSchema)
async def upload_srt(
    video_id: str,
    srt: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify video exists
    if not db.query(Video).filter(Video.video_id == video_id).first():
        raise HTTPException(status_code=404, detail="Video not found")

    # Check file extension
    if not srt.filename.lower().endswith('.srt'):
        raise HTTPException(status_code=400, detail="File must be a SRT file (.srt)")
    
    try:
        # Create temp directory and save file
        os.makedirs("tempsrt", exist_ok=True)
        safe_filename = sanitize_filename(srt.filename)
        srt_tmp = f"tempsrt/{safe_filename}"

        with open(srt_tmp, "wb") as buffer:
            shutil.copyfileobj(srt.file, buffer)
        
        # Create unique filename
        unique_srtname = f"0_{safe_filename}"
        count = 1
        while db.query(SRT).filter(SRT.srt_name == unique_srtname).first():
            unique_srtname = f"{count}_{safe_filename}"
        
        # Upload to S3
        s3.upload_file(srt_tmp, settings.AWS_BUCKET_TEST, unique_srtname)
        srt_url = f"https://{settings.AWS_BUCKET_TEST}.s3.amazonaws.com/{unique_srtname}"
        
        # Create SRT record with correct field names
        srt_data = SRTCreate(
            srt_name=unique_srtname,  # Changed from file_name
            srt_url=srt_url,         # Changed from file_url
            srt_url_sub=srt_url,
            video_id=video_id
        )
        
        return video_service.create_srt(db, srt_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        if os.path.exists(srt_tmp):
            os.remove(srt_tmp)

#  pass
@router.get("/srt/{video_id}", response_model=list[SRTSchema])
async def get_srt_by_video_id(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra xem video có tồn tại không
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    if not video_db:
        raise HTTPException(status_code=404, detail="Video not found")
    # Kiểm tra xem user có quyền truy cập không
    if current_user.user_id != video_db.user_id:
        raise HTTPException(status_code=403, detail="User not authorized to access")
    # download srt from s3
    os.makedirs("tempsrt", exist_ok=True)
    srt_tmp = "tempsrt/"
    srt_list = db.query(SRT).filter(SRT.video_id == video_id).all()
    for srt in srt_list:
        srt_name = srt.srt_name
        s3.download_file(settings.AWS_BUCKET_TEST, srt_name, f"{srt_tmp}{srt_name}")
    return video_service.get_srt_by_video_id(db, video_id)

#  pass
@router.get("/srt/{video_id}/{srt_id}", response_model=SRTSchema)
async def get_srt(
    srt_id: str,
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 
    srt_db = db.query(SRT).filter(SRT.srt_id == srt_id).first()
    if srt_db.video_id != video_id or not srt_db:
        raise HTTPException(status_code=404, detail="SRT not found")
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    if not video_db:
        raise HTTPException(status_code=404, detail="Video not found")
    if current_user.user_id != video_db.user_id:
        raise HTTPException(status_code=403, detail="User not authorized to access")
    # download srt from s3
    os.makedirs("tempsrtdl", exist_ok=True)
    srt_tmp = "tempsrtdl/"
    srt_db.srt_name = srt_db.srt_name.split("/")[-1]
    s3.download_file(settings.AWS_BUCKET_TEST, srt_db.srt_name, f"{srt_tmp}{srt_db.srt_name}")
    return video_service.get_srt_by_srt_id(db=db, video_id=video_id, srt_id=srt_id)

# pass
@router.delete("/srt/{srt_id}", response_model = None)
async def delete_srt(
    srt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra xem srt có tồn tại không
    if not db.query(SRT).filter(SRT.srt_id == srt_id).first():
        raise HTTPException(status_code=404, detail="SRT not found")
    # xoa srt tren s3
    srt = db.query(SRT).filter(SRT.srt_id == srt_id).first()
    s3.delete_object(Bucket=settings.AWS_BUCKET_TEST, Key = srt.srt_url.split("/")[-1])
    return video_service.delete_srt(db, srt_id)

# @router.put("/srt/{srt_id}", response_model = SRTSchema)
# async def update_srt(
#     srt_id: str,
#     srt: SRTUpdate,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     # Kiem tra Authorization
#     srt_db = db.query(SRT).filter(SRT.srt_id == srt_id).first()
#     if not srt_db:
#         raise HTTPException(status_code=404, detail="SRT not found")
#     video_db = db.query(Video).filter(Video.video_id == srt_db.video_id).first()
#     if not video_db:
#         raise HTTPException(status_code=404, detail="Video not found")
#     if current_user.user_id != video_db.user_id:
#         raise HTTPException(status_code=403, detail="User not authorized to access")
#     # Update
#     # Update srt tren s3
#     s3.copy_object(
#         Bucket=settings.AWS_BUCKET_TEST,
#         CopySource=f"{settings.AWS_BUCKET_TEST}/{srt_db.srt_url}",
#         Key=srt.srt_url
#     )
#     s3.copy_object(
#         Bucket=settings.AWS_BUCKET_TEST,
#         CopySource=f"{settings.AWS_BUCKET_TEST}/{srt_db.srt_url_sub}",
#         Key=srt.srt_url_sub
#     )
#     s3.delete_object(
#         Bucket=settings.AWS_BUCKET_TEST,
#         Key=srt_db.srt_url.split("/")[-1]
#     )
#     s3.delete_object(
#         Bucket=settings.AWS_BUCKET_TEST,
#         Key=srt_db.srt_url_sub.split("/")[-1]
#     )
#     return video_service.update_srt(db, srt_id, srt)


# Contact with VideoTTS
@router.post("/videotts/upload/{srt_id}", response_model=VideoTTSSchema)  
async def create_video_tts(
    srt_id: str,
    video_tts: VideoTTSCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra xem srt có tồn tại không
    srt = db.query(SRT).filter(SRT.srt_id == srt_id).first()
    if not srt:
        raise HTTPException(status_code=404, detail="SRT not found")
    
    video_tts.video_id = srt.video_id
    
    return video_service.create_video_tts(db, video_tts)

@router.get("/videotts/{video_id}", response_model=list[VideoTTSSchema])
async def get_video_tts(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra xem video có tồn tại không
    if not db.query(Video).filter(Video.video_id == video_id).first():
        raise HTTPException(status_code=404, detail="Video not found")
    
    return video_service.get_video_tts(db, video_id)

@router.get("/videotts/{video_tts_id}", response_model=VideoTTSSchema)
async def get_video_tts_by_id(
    video_tts_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra xem video có tồn tại không
    if not db.query(VIDEO_TTS).filter(VIDEO_TTS.video_tts_id == video_tts_id).first():
        raise HTTPException(status_code=404, detail="Video TTS not found")
    return video_service.get_video_tts_by_id(db, video_tts_id)



