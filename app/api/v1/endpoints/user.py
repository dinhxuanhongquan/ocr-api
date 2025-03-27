from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, BlackListToken
from app.schemas.user import UserCreate, UserUpdate, User as UserSchema
from app.service import user_service


router = APIRouter()

@router.post("/register", response_model=UserSchema)
async def register_user(
        user: UserCreate,
        db: Session = Depends(get_db)
        ):
    db_user = user_service.get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    db_user = user_service.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    return user_service.create_user(db, user)

@router.get("/me", response_model=UserSchema)
async def read_users_me(
        current_user: User = Depends(get_current_user)
        ):
    return current_user

@router.put("/me", response_model=UserSchema)
async def update_user_me(
        user: UserUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
        ):
    return user_service.update_user(db, current_user.user_id, user)
