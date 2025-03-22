from sqlalchemy import Column, String, DateTime
from app.models.base import BaseModel

class BlackListToken(BaseModel):
    __tablename__ = "blacklist_tokens"

    invalid_token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False) 