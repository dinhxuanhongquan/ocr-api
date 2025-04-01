from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.orm import validates
from app.core.database import Base
from app.core.config import utc_plus_7
import re
import uuid

#  Model User
class User(Base):
    __tablename__ = "user"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # Mật khẩu đã hash
    email = Column(String(100), unique=True, nullable=False)

    # Quan hệ với Video
    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)

    #  Validate email
    @validates("email")
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        return email
    

class BlackListToken(Base):
    __tablename__ = "black_list_token"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invalid_token = Column(String(255), nullable=False, unique=True)  # BLACK_LIST_{uid}_{jit}
    created_at = Column(DateTime, default=utc_plus_7)
