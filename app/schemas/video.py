from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class VideoBase(BaseModel):
    file_name: str
    file_url: str

class VideoUpdate(BaseModel):
    file_name: Optional[str] = None
    file_url: Optional[str] = None

class Video(VideoBase):
    video_id: str
    user_id: str
    created_at: datetime


    class Config:
        from_attributes = True



class SRTBase(BaseModel):
    srt_name: str
    srt_url: str
    srt_url_sub: str
    video_id: str

class SRTCreate(SRTBase):
    pass

class SRTUpdate(SRTBase):
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    file_sub_url: Optional[str] = None
    
class SRT(SRTBase):
    srt_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class VideoTTSBase(BaseModel):
    video_tts_name: str
    video_tts_url: str
    srt_id: str
    video_id: str

class VideoTTSUpdate(VideoTTSBase):
    video_tts_name: Optional[str] = None
    video_tts_url: Optional[str] = None

class VideoTTSCreate(VideoTTSBase):
    pass

class VideoTTS(VideoTTSBase):
    video_tts_id: str
    created_at: datetime

    class Config:
        from_attributes = True
