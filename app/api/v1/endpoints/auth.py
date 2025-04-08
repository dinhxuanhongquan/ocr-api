from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.core.database import get_db
from app.core.security import create_token, get_current_user
from app.service import user_service
from app.schemas.user import UserCreate,UserLogin, TokenRequest, Token as UserSchema
from app.models.user import User, BlackListToken
from datetime import datetime, timedelta
from app.core.config import get_settings
from app.core.config import utc_plus_7



settings = get_settings()
router = APIRouter()

@router.post("/token", response_model=UserSchema)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
        ):
    user = user_service.get_user_by_username(db, form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    if not user_service.verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, jit = create_token(user.user_id, user.username, access_token_expires)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "jit": jit
    }
@router.post("/login", response_model=UserSchema)
async def login_user(
        user: UserLogin,
        db: Session = Depends(get_db)
        ):
    db_user = user_service.get_user_by_username(db, user.username)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    if not user_service.verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    
    # Generate access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token, jit = create_token(db_user.user_id, db_user.username, access_token_expires)
    
    return JSONResponse(
        content=access_token,
        status_code=status.HTTP_200_OK
    )

@router.post("/logout", response_model=None)
async def logout(
        request: Request,
        db: Session = Depends(get_db)
        ):
    # Get token from request
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("uid")
        jit = payload.get("jit")

        if not all([user_id, jit]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Add token to blacklist
        blacklist_token = f"BLACK_LIST_{user_id}_{jit}"

        db_token = BlackListToken(
            invalid_token=blacklist_token
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
        

    db.add(db_token)
    db.commit()

    return {
        "Message": "Logged out successfully"
    }

