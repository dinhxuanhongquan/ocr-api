from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from starlette.background import BackgroundTask
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
from app.modules.video_process import extract_subtitles, translate_srt, compress_file
from app.modules.module.module_meger_video_with_srt_translate import add_subtitles_to_video
from app.modules.module.module_text_to_speech_v2 import generate_audio_from_srt
from app.modules.module.module_process_with_video_sync import process_video_with_sync
from app.modules.s3_process import upload_file_to_s3, download_file_from_s3, delete_file_from_s3, replace_file_on_s3
from app.modules.module.module_export_video import export_final_video
import boto3
import os
import shutil
import asyncio
import time
from pathlib import Path
import gc

def safe_remove_file(file_path, max_retries=5, delay=0.5):
    """Xoa file an toan voi co che thu lai nhieu lan"""
    path = Path(file_path)
    if not path.exists():
        return True
    
    for attempt in range(max_retries):
        try:
            path.unlink()
            return True
        except Exception as e:
            print(f"Warning: Failed to remove file {file_path}: {str(e)}")
            time.sleep(delay)
    return False


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
        # Extract and translate subtitles
        try:
            extract_subtitles(video_tmp, unique_srtname)
            translate_srt(srt_path, translate_srt_path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process subtitles: {str(e)}"
            )

        # Add subtitles to video
        add_subtitles_to_video(
            video_tmp,
            translate_srt_path,
            video_tmp
        )
        # Upload translated video to S3
        video_url = upload_file_to_s3(video_tmp, settings.AWS_BUCKET_INPUT_VIDEO)
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
                srt_url=upload_file_to_s3(srt_path, settings.AWS_BUCKET_INPUT_SRT),
                srt_url_sub=upload_file_to_s3(translate_srt_path, settings.AWS_BUCKET_INPUT_SRT), 
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
                settings.AWS_BUCKET_INPUT_SRT,
                file_paths["srt"]
            )
            download_file_from_s3(
                video_db.file_url,
                settings.AWS_BUCKET_INPUT_VIDEO,
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
        delete_file_from_s3(video_db.file_url, settings.AWS_BUCKET_INPUT_VIDEO)
        # Tai video moi len S3
        new_video_url = upload_file_to_s3(file_paths["video"], settings.AWS_BUCKET_INPUT_VIDEO)
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

# pass
@router.post("/creation/{video_id}/{voice}", response_model=None)
async def create_videotts(
    video_id: str,
    voice: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export a video file with subtitles to a new file.
    """
    # Validate video and SRT existence
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    srt_db = db.query(SRT).filter(SRT.video_id == video_id).first()
    
    if not video_db:
        raise HTTPException(status_code=404, detail="Video not found")
    if not srt_db:
        raise HTTPException(status_code=404, detail="SRT file not found")

    # Check user authorization
    if current_user.user_id != video_db.user_id:
        raise HTTPException(
            status_code=403,
            detail="User not authorized to access this video"
        )

    # Tạo đường dẫn thư mục tạm bằng pathlib để xử lý tương thích Windows tốt hơn
    temp_dirs = {
        "srt": Path("tempsrt"),
        "video": Path("tempvideo"),
        "audio": Path("tempaudio")
    }
    
    # Đảm bảo thư mục tạm tồn tại
    for dir_path in temp_dirs.values():
        dir_path.mkdir(exist_ok=True, parents=True)

    # Trích xuất tên file từ URL
    try:
        srt_filename = Path(srt_db.srt_url_sub).name
        video_filename = Path(video_db.file_url).name
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi xử lý tên file: {str(e)}"
        )

    # Định nghĩa đường dẫn file
    file_paths = {
        "srt": temp_dirs["srt"] / srt_filename,
        "video": temp_dirs["video"] / video_filename,
        "output_audio": temp_dirs["audio"] / "output_audio.mp3",
        "output_srt": temp_dirs["srt"] / "output_srt.srt",
        "output_video": temp_dirs["video"] / "output_final_video.mp4"
    }
    
    # Chuyển đường dẫn về string cho các hàm không hỗ trợ Path
    str_paths = {k: str(v) for k, v in file_paths.items()}
    
    try:
        # Tải file từ S3
        download_srt = download_file_from_s3(
            srt_db.srt_url_sub,
            settings.AWS_BUCKET_INPUT_SRT,
            str_paths["srt"]
        )
        download_video = download_file_from_s3(
            video_db.file_url,
            settings.AWS_BUCKET_INPUT_VIDEO,
            str_paths["video"]
        )
        
        if not download_srt or not download_video:
            raise HTTPException(
                status_code=500,
                detail="Không thể tải file từ S3"
            )
        
        # Tạo audio từ SRT
        loop = asyncio.get_event_loop()
        tts_audio_path = await loop.run_in_executor(
            None, 
            lambda: generate_audio_from_srt(str_paths["srt"], str(temp_dirs["audio"]), voice)
        )
        
        if not tts_audio_path:
            raise HTTPException(
                status_code=500,
                detail="Không thể tạo audio từ SRT"
            )
        
        # Xử lý video với audio và phụ đề
        process_video_with_sync(
            audio_file=tts_audio_path,
            video_file=str_paths["video"],
            srt_file=str_paths["srt"],
            output_audio=str_paths["output_audio"],
            output_srt=str_paths["output_srt"],
            output_video=str_paths["output_video"]
        )
        
        # Upload lên S3
        new_video_url = upload_file_to_s3(str_paths["output_video"], settings.AWS_BUCKET_VIDEO_SUB)
        new_srt_url = replace_file_on_s3(srt_db.srt_url_sub, settings.AWS_BUCKET_INPUT_SRT, str_paths["output_srt"])
        
        # Cập nhật database
        srt_updated = video_service.update_srt(
            db, 
            srt_db.srt_id, 
            SRTUpdate(
                srt_name=srt_db.srt_name, 
                srt_url_sub=new_srt_url,
                video_id=video_db.video_id,
                srt_url=srt_db.srt_url
            )
        )

        # Tạo video TTS mới
        video_tts = video_service.create_video_tts(
            db, 
            VideoTTSCreate(
                video_tts_name=video_db.file_name, 
                video_tts_url=new_video_url, 
                video_id=video_db.video_id, 
                srt_id=srt_db.srt_id
            )
        )
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "Xuất video thành công",
                "video_id": video_tts.video_tts_id,
                "filename": video_tts.video_tts_name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi không xác định: {str(e)}"
        )
    finally:
        # Đảm bảo file handle được đóng trước khi xóa
        gc.collect()
        time.sleep(0.5)  # Cho hệ thống thời gian để đóng file handle
        
        # Xóa file tạm với cơ chế thử lại nhiều lần
        all_paths = [str_paths["srt"], str_paths["video"], 
                    tts_audio_path if 'tts_audio_path' in locals() else None,
                    str_paths["output_audio"], str_paths["output_srt"], 
                    str_paths["output_video"]]
        
        for path in all_paths:
            if path is not None:
                try:
                    safe_remove_file(path)
                except Exception as e:
                    print(f"Cảnh báo: Không thể xóa file tạm {path}: {str(e)}")   

# testing
@router.get("/videotts/export/{video_tts_id}", response_model=None)
async def export_video_tts(
    video_tts_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export video TTS để người dùng tải xuống
    """
    # Kiểm tra video_tts tồn tại
    videotts_db = db.query(VIDEO_TTS).filter(VIDEO_TTS.video_tts_id == video_tts_id).first()
    if not videotts_db:
        raise HTTPException(status_code=404, detail="Video TTS không tìm thấy")
        
    # Kiểm tra video gốc tồn tại
    video_db = db.query(Video).filter(Video.video_id == videotts_db.video_id).first()
    if not video_db:
        raise HTTPException(status_code=404, detail="Video gốc không tìm thấy")
    
    # Kiểm tra quyền truy cập
    if current_user.user_id != video_db.user_id:
        raise HTTPException(status_code=403, detail="Người dùng không có quyền truy cập video này")
    
    # Tạo thư mục tạm
    temp_dirs = {
        "video": "tempvideo"
    }
    for dir_path in temp_dirs.values():
        os.makedirs(dir_path, exist_ok=True)
        
    try:
        # Lấy tên file
        video_tts_filename = os.path.basename(videotts_db.video_tts_url)
        
        # Đường dẫn tạm
        video_tts_tmp = os.path.join(temp_dirs["video"], video_tts_filename)
        
        # Tải từ S3
        download_success = download_file_from_s3(
            videotts_db.video_tts_url, 
            settings.AWS_BUCKET_VIDEO_SUB, 
            video_tts_tmp
        )
        
        if not download_success:
            raise HTTPException(status_code=500, detail="Không thể tải video từ kho lưu trữ")
        
        # Xuất video
        if export_final_video(video_tts_tmp):
            return FileResponse(
                video_tts_tmp,
                media_type="video/mp4",
                filename=f"{video_tts_filename}",
                background=BackgroundTask(lambda: safe_remove_file(video_tts_tmp))
            )
        else:
            raise HTTPException(status_code=500, detail="Không thể xuất video")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi không xác định: {str(e)}")   

# Get sound 

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
            new_srt_url = replace_file_on_s3(srt_db.srt_url, settings.AWS_BUCKET_INPUT_SRT, file_paths["srt"])
            new_srt_sub_url = replace_file_on_s3(srt_db.srt_url_sub, settings.AWS_BUCKET_INPUT_SRT, file_paths["srt_sub"])
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
@router.get("/", response_model=None)
async def get_videos(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách video của người dùng kèm preview"""
    videos = video_service.get_user_videos(db, current_user.user_id, skip, limit)
    
    # Tạo thư mục tạm cho thumbnails
    temp_dir = "temp_thumbnails"
    os.makedirs(temp_dir, exist_ok=True)
    
    response_videos = []
    for video in videos:
        # Tạo response object cho mỗi video
        video_data = {
            "video_id": video.video_id,
            "file_name": video.file_name,
            "file_url": video.file_url,
            "created_at": video.created_at.isoformat() if video.created_at else None
        }
        
        # Tạo thumbnail từ video
        try:
            # Tên file thumbnail
            thumbnail_filename = f"{video.video_id}_thumb.jpg"
            thumbnail_path = os.path.join(temp_dir, thumbnail_filename)
            
            # Kiểm tra xem thumbnail đã tồn tại chưa
            if not os.path.exists(thumbnail_path):
                # Tải video từ S3
                video_tmp = os.path.join("tempvideo", os.path.basename(video.file_url))
                os.makedirs("tempvideo", exist_ok=True)
                
                download_success = download_file_from_s3(
                    video.file_url,
                    settings.AWS_BUCKET_INPUT_VIDEO,
                    video_tmp
                )
                
                if download_success:
                    # Tạo thumbnail bằng FFmpeg
                    import subprocess
                    command = [
                        "ffmpeg", "-y", "-i", video_tmp,
                        "-ss", "00:00:05",  # Lấy frame ở giây thứ 5
                        "-frames:v", "1",   # Chỉ lấy 1 frame
                        "-vf", "scale=320:-1",  # Resize về chiều rộng 320px
                        "-q:v", "2",        # Chất lượng thumbnail
                        thumbnail_path
                    ]
                    subprocess.run(command, capture_output=True)
                    
                    # Upload thumbnail lên S3 - SỬA DÒNG NÀY
                    # Đổi tên file trước khi upload để có đường dẫn đúng
                    thumbnail_s3_name = f"thumbnails/{thumbnail_filename}"
                    with open(thumbnail_path, "rb") as f:
                        s3.upload_fileobj(
                            f,
                            settings.AWS_BUCKET_INPUT_VIDEO, 
                            thumbnail_s3_name
                        )
                    
                    # Xóa file video tạm
                    safe_remove_file(video_tmp)
                
            # Đọc thumbnail dưới dạng base64
            if os.path.exists(thumbnail_path):
                import base64
                with open(thumbnail_path, "rb") as img_file:
                    thumbnail_b64 = base64.b64encode(img_file.read()).decode("utf-8")
                video_data["thumbnail"] = f"data:image/jpeg;base64,{thumbnail_b64}"
        except Exception as e:
            print(f"Không thể tạo thumbnail cho video {video.video_id}: {str(e)}")
            video_data["thumbnail"] = None
        
        response_videos.append(video_data)
        # Xóa thumbnail sau khi su dung
        if os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
            except Exception as e:
                print(f"Không thể xóa thumbnail {thumbnail_path}: {str(e)}")    
    return JSONResponse(
        status_code=200,
        content={"videos": response_videos}
    )



# pass
@router.get("/{video_id}")
async def get_video_by_id(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    if not video_db:
        raise HTTPException(status_code=404, detail="Video not exist")
    if current_user.user_id != video_db.user_id:
        raise HTTPException(status_code=403, detail="User not authorized to access this video")
    # download video from s3
    temp_dirs = {
        "video": "tempvideo"
    }
    for dir_path in temp_dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    # Extract filenames from URLs
    try:
        video_filename = os.path.basename(video_db.file_url)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file names: {str(e)}"
        )
    # Define file paths
    video_tmp = os.path.join(temp_dirs["video"], video_filename)
    # Download video from S3
    download_file_from_s3(video_db.file_url, settings.AWS_BUCKET_INPUT_VIDEO, video_tmp)
    return FileResponse(
        path=video_tmp,
        media_type="video/mp4",
        filename=video_filename
    )  


#pass
@router.get("/videotts/{video_tts_id}", response_model=None)
async def get_video_tts_by_id(
    video_tts_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Kiểm tra xem video có tồn tại không
    video_tts_db = db.query(VIDEO_TTS).filter(VIDEO_TTS.video_tts_id == video_tts_id).first()
    video_db = db.query(Video).filter(Video.video_id == video_tts_db.video_id).first()
    if not video_tts_db:
        raise HTTPException(status_code=404, detail="Video not found")
    if current_user.user_id != video_db.user_id:
        raise HTTPException(status_code=403, detail="User not authorized to access")
    
    # download video tts from s3
    temp_dirs = {
        "video": "tempvideo"
    }
    for dir_path in temp_dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    # Extract filenames from URLs
    try:
        video_filename = os.path.basename(video_tts_db.video_tts_url)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file names: {str(e)}"
        )
    # Define file paths
    video_tmp = os.path.join(temp_dirs["video"], video_filename)
    # Download video from S3
    download_file_from_s3(video_tts_db.video_tts_url, settings.AWS_BUCKET_VIDEO_SUB, video_tmp)
    return FileResponse(
        path=video_tmp,
        media_type="video/mp4",
        filename=video_filename
    )

@router.get("/videottses/{video_id}", response_model=None)
async def get_videottses(
    video_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách video của người dùng kèm preview"""
    videottses = video_service.get_video_tts(db, video_id, skip, limit)
    
    # Tạo thư mục tạm cho thumbnails
    temp_dir = "temp_thumbnails"
    os.makedirs(temp_dir, exist_ok=True)
    
    response_videos = []
    for videotts in videottses:
        # Tạo response object cho mỗi video
        video_data = {
            "video_id": videotts.video_tts_id,
            "file_name": videotts.video_tts_name,
            "file_url": videotts.video_tts_url,
            "created_at": videotts.created_at.isoformat() if videotts.created_at else None
        }
        
        # Tạo thumbnail từ video
        try:
            # Tên file thumbnail
            thumbnail_filename = f"{videotts.video_tts_id}_thumb.jpg"
            thumbnail_path = os.path.join(temp_dir, thumbnail_filename)
            
            # Kiểm tra xem thumbnail đã tồn tại chưa
            if not os.path.exists(thumbnail_path):
                # Tải video từ S3
                video_tmp = os.path.join("tempvideo", os.path.basename(videotts.video_tts_url))
                os.makedirs("tempvideo", exist_ok=True)
                
                download_success = download_file_from_s3(
                    videotts.video_tts_url,
                    settings.AWS_BUCKET_VIDEO_SUB,
                    video_tmp
                )
                
                if download_success:
                    # Tạo thumbnail bằng FFmpeg
                    import subprocess
                    command = [
                        "ffmpeg", "-y", "-i", video_tmp,
                        "-ss", "00:00:05",  # Lấy frame ở giây thứ 5
                        "-frames:v", "1",   # Chỉ lấy 1 frame
                        "-vf", "scale=320:-1",  # Resize về chiều rộng 320px
                        "-q:v", "2",        # Chất lượng thumbnail
                        thumbnail_path
                    ]
                    subprocess.run(command, capture_output=True)
                    
                    # Upload thumbnail lên S3 - SỬA DÒNG NÀY
                    # Đổi tên file trước khi upload để có đường dẫn đúng
                    thumbnail_s3_name = f"thumbnails/{thumbnail_filename}"
                    with open(thumbnail_path, "rb") as f:
                        s3.upload_fileobj(
                            f,
                            settings.AWS_BUCKET_VIDEO_SUB, 
                            thumbnail_s3_name
                        )
                    
                    # Xóa file video tạm
                    safe_remove_file(video_tmp)

            # Đọc thumbnail dưới dạng base64
            if os.path.exists(thumbnail_path):
                import base64
                with open(thumbnail_path, "rb") as img_file:
                    thumbnail_b64 = base64.b64encode(img_file.read()).decode("utf-8")
                video_data["thumbnail"] = f"data:image/jpeg;base64,{thumbnail_b64}"
        except Exception as e:
            print(f"Không thể tạo thumbnail cho video {videotts.video_tts_id}: {str(e)}")
            video_data["thumbnail"] = None
        
        response_videos.append(video_data)
        # Xoa thumbnail sau khi sử dụng
        try:
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        except Exception as e:
            print(f"Warning: Failed to remove thumbnail file {thumbnail_path}: {str(e)}")
    return JSONResponse(
        status_code=200,
        content={"videos": response_videos}
    )





# pass
@router.delete("/{video_id}", response_model=None)
async def delete_video_by_id(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # xoa video tren s3
    video_db = db.query(Video).filter(Video.video_id == video_id).first()
    srt_db = db.query(SRT).filter(SRT.video_id == video_db.video_id).first()
    videotts_db = db.query(VIDEO_TTS).filter(VIDEO_TTS.video_id == video_db.video_id).first()
    if not video_db:
        raise HTTPException(status_code=404, detail="Video not found")
    if current_user.user_id != video_db.user_id:
        raise HTTPException(status_code=403, detail="User not authorized to delete this video")
    # xoa video tren s3
    delete_file_from_s3(video_db.file_url, settings.AWS_BUCKET_INPUT_VIDEO)
    delete_file_from_s3(srt_db.srt_url, settings.AWS_BUCKET_INPUT_SRT)
    delete_file_from_s3(srt_db.srt_url_sub, settings.AWS_BUCKET_INPUT_SRT)
    delete_file_from_s3(videotts_db.video_tts_url, settings.AWS_BUCKET_VIDEO_SUB)
    return video_service.delete_video(db, video_id)

#  pass
@router.get("/srt/{video_id}/original", response_model=None)
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
    srt_db = db.query(SRT).filter(SRT.video_id == video_id).first()
    if not srt_db:
        raise HTTPException(status_code=404, detail="SRT not found")
    # download srt from s3
    temp_dirs = {
        "srt": "tempsrt",
    }
    for dir_path in temp_dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    # Extract filenames from URLs
    try:
        srt_filename = os.path.basename(srt_db.srt_url)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file names: {str(e)}"
        )
    # Define file paths
    srt_tmp = os.path.join(temp_dirs["srt"], srt_filename)
    # Download video from S3
    download_file_from_s3(srt_db.srt_url, settings.AWS_BUCKET_INPUT_SRT, srt_tmp)
    return FileResponse(
        path=srt_tmp,
        media_type="application/x-subrip",
        filename=srt_filename
    )


# pass
@router.get("/srt/{video_id}/translated", response_model=None)
async def get_srt_trans_by_video_id(
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
    srt_db = db.query(SRT).filter(SRT.video_id == video_id).first()
    if not srt_db:
        raise HTTPException(status_code=404, detail="SRT not found")
    # download srt from s3
    temp_dirs = {
        "srt": "tempsrt",
    }
    for dir_path in temp_dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    # Extract filenames from URLs
    try:
        srt_sub_filename = os.path.basename(srt_db.srt_url_sub)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file names: {str(e)}"
        )
    # Define file paths
    srt_sub_tmp = os.path.join(temp_dirs["srt"], srt_sub_filename)
    # Download video from S3
    download_file_from_s3(srt_db.srt_url_sub, settings.AWS_BUCKET_INPUT_SRT, srt_sub_tmp)
    return FileResponse(
        path=srt_sub_tmp,
        media_type="application/x-subrip",
        filename=srt_sub_filename
    )



