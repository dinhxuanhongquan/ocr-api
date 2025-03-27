from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserUpdate, User, TokenRequest, Token
from .database import get_db
from app.models.user import User, BlackListToken
from app.core.config import get_settings
import uuid

# Get settings
settings = get_settings()
# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", scheme_name="JWT")
# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(
        plain_password: str, 
        hashed_password: str
        ) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(
        password: str
        ) -> str:
    return pwd_context.hash(password)

def create_token(
        user_id: str, 
        username: str,
        expires_delta: Optional[timedelta] = None
        ) -> tuple[str, str]:
    jit = str(uuid.uuid4())  # Generate unique JIT for each login
    
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    
    data = {
        "sub": username,
        "uid": user_id,
        "jit": jit,
        "exp": expire
    }
    encoded_jwt = jwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt, jit

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token.split(' ')[1]
            
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("uid")
        jit: str = payload.get("jit")
        
        if not all([username, user_id, jit]):
            raise credentials_exception
            
        # Check if token is blacklisted
        blacklist_token = f"BLACK_LIST_{user_id}_{jit}"
        blacklisted = db.query(BlackListToken).filter(
            BlackListToken.invalid_token == blacklist_token
        ).first()
        if blacklisted:
            raise credentials_exception
            
        user = db.query(User).filter(
            User.username == username,
            User.user_id == user_id
        ).first()
        if user is None:
            raise credentials_exception
        return user
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
