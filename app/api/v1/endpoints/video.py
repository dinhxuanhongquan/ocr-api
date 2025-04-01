from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
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
from app.modules.video_process import extract_subtitles, translate_srt, compress_file
from app.modules.module.module_meger_video_with_srt_translate import add_subtitles_to_video
from app.modules.module.module_text_to_speech_v2 import generate_audio_from_srt
from app.modules.module.module_process_with_video_sync import process_video_with_sync
from app.modules.s3_process import upload_file_to_s3, download_file_from_s3, delete_file_from_s3, replace_file_on_s3
import boto3
import os
import shutil
from pathlib import Path
import asyncio


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
    """
    Upload a video file, extract subtitles, translate them, and save to database.
    
    Args:
        video: The video file to upload
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        JSONResponse with success message
        
    Raises:
        HTTPException for various error conditions
    """
    # Validate file type
    if not video.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only video files are allowed."
        )

    # Create temp directories if they don't exist
    os.makedirs("tempvideo", exist_ok=True)
    os.makedirs("tempsrt", exist_ok=True)

    # Generate unique filenames
    video_filename = os.path.splitext(video.filename)[0]
    unique_videoname = f"0_{video.filename}"
    unique_srtname = f"{video_filename}_subtitles.srt"
    translate_srtname = f"{video_filename}_translate.srt"

    # Generate unique video name
    count = 1
    while db.query(Video).filter(Video.file_name == unique_videoname).first():
        unique_videoname = f"{count}_{video.filename}"
        count += 1

    # Define paths
    video_tmp = os.path.join("tempvideo", video.filename)
    srt_path = os.path.join("tempsrt", unique_srtname)
    translate_srt_path = os.path.join("tempsrt", translate_srtname)

    try:
        # Save uploaded video
        with open(video_tmp, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        # Compress and upload video to S3
        # compress_file(video_tmp, video_tmp)
        video_url = upload_file_to_s3(video_tmp, settings.AWS_BUCKET_TEST)

        # Extract and translate subtitles
        try:
            extract_subtitles(video_tmp, unique_srtname)
            translate_srt(srt_path, translate_srt_path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process subtitles: {str(e)}"
            )

        # Save video to database
        try:
            db_video = video_service.create_video(
                db,
                VideoUpdate(file_name=unique_videoname, file_url=video_url),
                current_user.user_id
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save video to database: {str(e)}"
            )

        # Save SRT files to database
        try:
            video_service.create_srt(
            db, 
            SRTCreate(
                srt_name=unique_srtname, 
                srt_url=upload_file_to_s3(srt_path, settings.AWS_BUCKET_TEST),
                srt_url_sub=upload_file_to_s3(translate_srt_path, settings.AWS_BUCKET_TEST), 
                video_id=db_video.video_id
                )
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save subtitles to database: {str(e)}"
            )

        return JSONResponse(
            status_code=201,
            content={
                "message": "Video uploaded successfully",
                "video_id": db_video.video_id,
                "filename": unique_videoname
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )
    finally:
        # Cleanup temporary  all files
        for file_path in [video_tmp, srt_path, translate_srt_path, ]:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Warning: Failed to remove temporary file {file_path}: {str(e)}")

# pass
@router.post("/subtitles/{video_id}", response_model=SRTSchema)
async def add_subtitles_to_video_endpoint(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add subtitles to a video file.
    
    Args:
        video_id: ID of the video to add subtitles to
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        JSONResponse with success message
        
    Raises:
        HTTPException for various error conditions
    """
    # Validate video and SRT existence
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    srt_db = db.query(SRT).filter(SRT.video_id == video_id).first()
    
    if not video_db:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )
    if not srt_db:
        raise HTTPException(
            status_code=404,
            detail="SRT file not found"
        )

    # Check user authorization
    if current_user.user_id != video_db.user_id:
        raise HTTPException(
            status_code=403,
            detail="User not authorized to access this video"
        )

    # Create temporary directories
    temp_dirs = {
        "srt": "tempsrt",
        "video": "tempvideo"
    }
    for dir_path in temp_dirs.values():
        os.makedirs(dir_path, exist_ok=True)

    # Extract filenames from URLs
    try:
        srt_filename = os.path.basename(srt_db.srt_url_sub)
        video_filename = os.path.basename(video_db.file_url)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file names: {str(e)}"
        )

    # Define file paths
    file_paths = {
        "srt": os.path.join(temp_dirs["srt"], srt_filename),
        "video": os.path.join(temp_dirs["video"], video_filename)
    }

    try:
        # Download files from S3
        try:
            download_file_from_s3(
                srt_db.srt_url_sub,
                settings.AWS_BUCKET_TEST,
                file_paths["srt"]
            )
            download_file_from_s3(
                video_db.file_url,
                settings.AWS_BUCKET_TEST,
                file_paths["video"]
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download files from S3: {str(e)}"
            )

        # Add subtitles to video
        add_subtitles_to_video(
            file_paths["video"],
            file_paths["srt"],
            file_paths["video"]
        )
        # xoa video cu tren s3
        delete_file_from_s3(video_db.file_url, settings.AWS_BUCKET_TEST)
        # Tai video moi len S3
        new_video_url = upload_file_to_s3(file_paths["video"], settings.AWS_BUCKET_TEST)
        # Update video URL in database
        video = video_service.update_video(db, video_id, VideoUpdate(file_url=new_video_url))
        return JSONResponse(
            status_code=201,
            content={
                "message": "Subtitles added successfully",
                "video_id": video.video_id,
                "filename": video.file_name
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
    finally:
        # Cleanup temporary files
        for file_path in file_paths.values():
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Warning: Failed to remove temporary file {file_path}: {str(e)}")


@router.post("/export/{video_id}/{voice}", response_model=None)
async def export_video(
    video_id: str,
    voice: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export a video file with subtitles to a new file.
    
    Args:
        video_id: ID of the video to export
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        JSONResponse with success message
        
    Raises:
        HTTPException for various error conditions
    """
    # Validate video and SRT existence
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    srt_db = db.query(SRT).filter(SRT.video_id == video_id).first()
    
    if not video_db:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )
    if not srt_db:
        raise HTTPException(
            status_code=404,
            detail="SRT file not found"
        )

    # Check user authorization
    if current_user.user_id != video_db.user_id:
        raise HTTPException(
            status_code=403,
            detail="User not authorized to access this video"
        )

    # Create temporary directories
    temp_dirs = {
        "srt": "tempsrt",
        "video": "tempvideo",
        "audio": "tempaudio"
    }
    for dir_path in temp_dirs.values():
        os.makedirs(dir_path, exist_ok=True)

    # Extract filenames from URLs
    try:
        srt_filename = os.path.basename(srt_db.srt_url_sub)
        video_filename = os.path.basename(video_db.file_url)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file names: {str(e)}"
        )

    # Define file paths
    file_paths = {
        "srt": os.path.join(temp_dirs["srt"], srt_filename),
        "video": os.path.join(temp_dirs["video"], video_filename)
    }
    try:
        # Download files from S3
        dowload_srt = download_file_from_s3(
            srt_db.srt_url_sub,
            settings.AWS_BUCKET_TEST,
            file_paths["srt"]
        )
        download_video = download_file_from_s3(
            video_db.file_url,
            settings.AWS_BUCKET_TEST,
            file_paths["video"]
        )
        if not dowload_srt or not download_video:
            raise HTTPException(
                status_code=500,
                detail="Failed to download files from S3"
            )
        
        # Generate audio from SRT
        loop = asyncio.get_event_loop()
        tts_audio_path = await loop.run_in_executor(
            None, 
            lambda: generate_audio_from_srt(file_paths["srt"], temp_dirs["audio"], voice)
        )
        
        if not tts_audio_path:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate audio from SRT"
            )
        
        # Process video with audio and subtitles
        process_video_with_sync(
            audio_file=tts_audio_path,
            video_file=file_paths["video"],
            srt_file=file_paths["srt"],
            output_audio=os.path.join(temp_dirs["audio"], "output_audio.mp3"),
            output_srt=os.path.join(temp_dirs["srt"], "output_srt.srt"),
            output_video=os.path.join(temp_dirs["video"], "output_final_video.mp4")
        )
        # Tai video tts len S3
        new_video_url = upload_file_to_s3(os.path.join(temp_dirs["video"], "output_final_video.mp4"), settings.AWS_BUCKET_TEST)
        # Craete new video tts
        video_tts = video_service.create_video_tts(db, VideoTTSCreate(video_tts_name=video_db.file_name, video_tts_url=new_video_url, video_id=video_db.video_id, srt_id=srt_db.srt_id))
        return JSONResponse(
            status_code=201,
            content={
                "message": "Video exported successfully",
                "video_id": video_tts.video_tts_id,
                "filename": video_tts.video_tts_name
            }
        ) 
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
    finally:
        # Cleanup temporary files
        for file_path in file_paths.values():
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Warning: Failed to remove temporary file {file_path}: {str(e)}")
      
# Update SRT file when user changed it
# pass
@router.put("/srt/upload/{video_id}", response_model=SRTSchema)
async def upload_srt(
    video_id: str,
    srt: UploadFile = File(...),
    srt_sub: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a SRT file and save to database.
    
    Args:
        video_id: ID of the video to add subtitles to
        srt: The SRT file to upload
        db: Database session
        current_user: Current authenticated user
        
        Returns:
        JSONResponse with success message
        
        Raises:
        HTTPException for various error conditions
    """
    # validate file type
    # if not srt.filename.lower().endswith('.srt'):
    #     raise HTTPException(
    #         status_code=400,
    #         detail="Invalid file type. Only SRT files are allowed."
    #     )
    if not srt_sub.filename.lower().endswith('.srt'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only SRT files are allowed."
        )
    
    # Validate video and SRT existence
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    srt_db = db.query(SRT).filter(SRT.video_id == video_db.video_id).first()

    if not video_db:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        ) 
    if not srt_db:
        raise HTTPException(
            status_code=404,
            detail="SRT file not found"
        )
    
    # Check user authorization
    if current_user.user_id != video_db.user_id:
        raise HTTPException(
            status_code=403,
            detail="User not authorized to access this video"
        )
    
    # Create temporary directories
    temp_dirs = {
        "srt": "tempsrt"    
        }

    for dir_path in temp_dirs.values():
        os.makedirs(dir_path, exist_ok=True)

    # Generate unique filenames
    srt_subtitle = os.path.basename(srt_db.srt_url)
    srt_translate = os.path.basename(srt_db.srt_url_sub)

    # Define file paths
    file_paths = {
        "srt": os.path.join(temp_dirs["srt"], srt_subtitle),
        "srt_sub": os.path.join(temp_dirs["srt"], srt_translate)
    }

    try:
        # Save uploaded files
        with open(file_paths["srt"], "wb") as buffer:
            shutil.copyfileobj(srt.file, buffer)
        with open(file_paths["srt_sub"], "wb") as buffer:
            shutil.copyfileobj(srt_sub.file, buffer)

        # Replace old SRT files with new ones
        try:
            new_srt_url = replace_file_on_s3(srt_db.srt_url, settings.AWS_BUCKET_TEST, file_paths["srt"])
            new_srt_sub_url = replace_file_on_s3(srt_db.srt_url_sub, settings.AWS_BUCKET_TEST, file_paths["srt_sub"])
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update SRT files in S3: {str(e)}"
            )
        srt_updated = video_service.update_srt(db, srt_db.srt_id, SRTUpdate(
            srt_name=srt_db.srt_name, 
            srt_url=new_srt_url, 
            srt_url_sub=new_srt_sub_url,
            video_id=video_db.video_id
        ))

        return JSONResponse(
            status_code=201,
            content={
                "message": "SRT files uploaded successfully",
                "srt_id": srt_updated.srt_id,
                "filename": srt_updated.srt_name
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
    finally:
        # Cleanup temporary files
        for file_path in file_paths.values():
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Warning: Failed to remove temporary file {file_path}: {str(e)}")



    

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
    # download video from s3
    os.makedirs("tempvideodowload", exist_ok=True)
    video_tmp = "tempvideodowload/"
    video_db.file_name = video_db.file_name.split("/")[-1]
    if download_file_from_s3(video_db.file_url, settings.AWS_BUCKET_TEST, video_tmp):
        return video_service.get_video(db, video_id)
    else :
        raise HTTPException(
            status_code=500,
            detail="Failed to download video from S3"
        )

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
            new_url = replace_file_on_s3(db_video.file_name, video_update.file_name, settings.AWS_BUCKET_TEST)
            # Update URL
            video_update.file_url = new_url
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

@router.put("/srt/{srt_id}", response_model = SRTSchema)
async def update_srt(
    srt_id: str,
    srt: SRTUpdate,

    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiem tra Authorization
    srt_db = db.query(SRT).filter(SRT.srt_id == srt_id).first()
    if not srt_db:
        raise HTTPException(status_code=404, detail="SRT not found")
    video_db = db.query(Video).filter(Video.video_id == srt_db.video_id).first()
    if not video_db:
        raise HTTPException(status_code=404, detail="Video not found")
    if current_user.user_id != video_db.user_id:
        raise HTTPException(status_code=403, detail="User not authorized to access")
    # Update
    # Update srt tren s3
    s3.copy_object(
        Bucket=settings.AWS_BUCKET_TEST,
        CopySource=f"{settings.AWS_BUCKET_TEST}/{srt_db.srt_url}",
        Key=srt.srt_url
    )
    s3.copy_object(
        Bucket=settings.AWS_BUCKET_TEST,
        CopySource=f"{settings.AWS_BUCKET_TEST}/{srt_db.srt_url_sub}",
        Key=srt.srt_url_sub
    )
    s3.delete_object(
        Bucket=settings.AWS_BUCKET_TEST,
        Key=srt_db.srt_url.split("/")[-1]
    )
    s3.delete_object(
        Bucket=settings.AWS_BUCKET_TEST,
        Key=srt_db.srt_url_sub.split("/")[-1]
    )
    return video_service.update_srt(db, srt_id, srt)


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



