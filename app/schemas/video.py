from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class VideoBase(BaseModel):
    name: str
    metadata: Optional[Dict[str, Any]] = {}

class VideoCreate(VideoBase):
    pass

class VideoUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class VideoInDBBase(VideoBase):
    id: str
    user_id: str
    s3_key: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Video(VideoInDBBase):
    pass

class VideoInDB(VideoInDBBase):
    pass 