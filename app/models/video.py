from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Video(BaseModel):
    __tablename__ = "videos"

    name = Column(String(255), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    s3_key = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")
    metadata = Column(JSON, default={})

    user = relationship("User", back_populates="videos") 