from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import re
from sqlalchemy.orm import validates
from urllib.parse import quote_plus
import uuid

# Create database engine - properly escape special characters in password
# password = quote_plus("090203Qu@n")  # URL encode the password
# SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://root:{password}@localhost:3306/video_ocr"
# engine = create_engine(SQLALCHEMY_DATABASE_URL)
password = quote_plus("Abc123456")  # URL encode the password
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://admin:{password}@db-sub-video.c1siqkqs2a46.ap-southeast-2.rds.amazonaws.com:3306/db_sub_video"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

class User(Base):
    __tablename__ = "user"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # This will store hashed password
    email = Column(String(100), unique=True, nullable=False)
    
    # Relationship with videos
    videos = relationship("Video", back_populates="user")

    @validates('email')
    def validate_email(self, key, email):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email format")
        return email

class Video(Base):
    __tablename__ = "videos"

    video_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("user.user_id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    
    # Relationship with user
    user = relationship("User", back_populates="videos")

class BlackListToken(Base):
    __tablename__ = "black_list_token"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invalid_token = Column(String(255), nullable=False, unique=True)  # Format: BLACK_LIST_{uid}_{jit}
    created_at = Column(DateTime, default=datetime.utcnow)

# Create all tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 