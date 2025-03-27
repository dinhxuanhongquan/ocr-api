from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.schemas.user import UserCreate, UserUpdate, User, TokenRequest, Token
from app.models.user import User 
from app.core.security import verify_password, get_password_hash, create_token

def create_user(
        db: Session, 
        user: UserCreate
        ):
    db_user = User(
        username=user.username,
        email=user.email,
        password=get_password_hash(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(
        db: Session,
        user_id: str
        ):
    return db.query(User).filter(User.user_id == user_id).first()

def get_user_by_username(
        db: Session,
        username:str
        ):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(
        db: Session,
        email: str
        ):
    # kiem tra co dung la 1 email hay khong
    if not "@" in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email"
        )
    return db.query(User).filter(User.email == email).first()

def get_users(
        db: Session,
        skip: int = 0,
        limit: int = 100
        ):
    return db.query(User).offset(skip).limit(limit).all()


def update_user(
        db: Session,
        user_id: str,
        user_update: UserUpdate
        ):
    db_user = db.query(User).filter(User.user_id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # get old value of user
    old_username = db_user.username
    old_email = db_user.email
    old_password = db_user.password

    # update username if it is not None
    if user_update.username is not None:
        existing_user = db.query(User).filter(User.username == user_update.username).first()
        if existing_user and existing_user.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        db_user.username = user_update.username
    else:
        db_user.username = old_username
    # update email if it is not None
    if user_update.email is not None:
        if not "@" in user_update.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email"
            )
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user and existing_user.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        db_user.email = user_update.email
    else:
        db_user.email = old_email

    
    # update password if it is not None
    if user_update.password is not None:
        db_user.password = get_password_hash(user_update.password)
    else:
        db_user.password = old_password

    db.commit()
    db.refresh(db_user)
    return db_user

def update_password(
        db: Session,
        user_id: str,
        password: str
        ):
    db_user = db.query(User).filter(User.user_id == user_id).first()
    if db_user:
        db_user.password = get_password_hash(password)
        db.commit()
        db.refresh(db_user)
        return db_user
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
def authenticate_user(
        db: Session, 
        username: str, 
        password: str
        ):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user
