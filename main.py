from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr
import shutil
import os
from database import User, Video, BlackListToken, get_db
from sqlalchemy.orm import Session
import s3
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
import httpx
import uuid

app = FastAPI(title="Video Translation API")

# Add SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv('SESSION_SECRET_KEY', 'your-secret-key-here'),
    session_cookie="session"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 configuration
config = Config('.env')
oauth = OAuth(config)

# Load Google credentials from environment variables
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Load Microsoft credentials from environment variables
oauth.register(
    name='microsoft',
    client_id=os.getenv('MICROSOFT_CLIENT_ID'),
    client_secret=os.getenv('MICROSOFT_CLIENT_SECRET'),
    server_metadata_url='https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

# JWT setup
SECRET_KEY = "/EyY1GnelIliNbL0Lempu5rEAzVZ5xQ4GWvO1dOTml0ouAA7EAmM5c84BoZPYlFi"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user

def create_token(user_id: str, username: str):
    jit = str(uuid.uuid4())  # Generate unique JIT for each login
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    data = {
        "sub": username,
        "uid": user_id,
        "jit": jit,
        "exp": expire
    }
    encoded_jwt = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, jit

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    except JWTError:
        raise credentials_exception

@app.get('/login/google')
async def google_login(request: Request, db: Session = Depends(get_db)):
    try:
        # Get token from Google
        token = await oauth.google.authorize_access_token(request)
        if not token:
            raise HTTPException(status_code=400, detail="Failed to get token from Google")
        
        # Get user info
        user_info = token.get('userinfo')
        if not user_info or 'email' not in user_info:
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")

        # Check if user exists or create new one
        db_user = db.query(User).filter(User.email == user_info['email']).first()
        if not db_user:
            username = user_info['email'].split('@')[0]
            while db.query(User).filter(User.username == username).first():
                username = f"{username}{os.urandom(2).hex()}"
            
            db_user = User(
                username=username,
                email=user_info['email'],
                password=get_password_hash(os.urandom(32).hex())
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)

        # Create JWT token
        access_token, jit = create_token(db_user.user_id, db_user.username)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "jit": jit,
            "user": {
                "user_id": db_user.user_id,
                "username": db_user.username,
                "email": db_user.email
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Google authentication failed: {str(e)}"
        )

@app.get('/login/microsoft')
async def microsoft_login(request: Request):
    redirect_uri = request.url_for('microsoft_auth')
    return await oauth.microsoft.authorize_redirect(request, redirect_uri)

@app.get('/auth/microsoft')
async def microsoft_auth(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.microsoft.authorize_access_token(request)
        user_info = token.get('userinfo')
        if user_info:
            # Check if user exists
            db_user = db.query(User).filter(User.email == user_info['email']).first()
            if not db_user:
                # Create new user
                db_user = User(
                    username=user_info['email'].split('@')[0],
                    email=user_info['email'],
                    password=get_password_hash(os.urandom(32).hex())  # Random secure password
                )
                db.add(db_user)
                db.commit()
                db.refresh(db_user)
            
            # Create access token
            access_token, _ = create_token(db_user.user_id, db_user.username)
            return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User created successfully"}

@app.post("/token")
async def get_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token, jit = create_token(user.user_id, user.username)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email
        }
    }

@app.post("/logout")
async def logout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # Get token from authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("uid")
        jit = payload.get("jit")
        
        # Create blacklist token string
        blacklist_token = f"BLACK_LIST_{user_id}_{jit}"
        
        # Add to blacklist
        db_blacklist = BlackListToken(
            invalid_token=blacklist_token
        )
        db.add(db_blacklist)
        db.commit()
        
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/videos/upload")
async def upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    # Create temp directory if it doesn't exist
    os.makedirs("temp", exist_ok=True)
    
    temp_file = f"temp/{file.filename}"
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Upload to S3
        s3.s3_client.upload_file(temp_file, s3.bucket_name, file.filename)
        file_url = f"https://{s3.bucket_name}.s3.amazonaws.com/{file.filename}"

        # Save video information to database
        video = Video(
            file_name=file.filename,
            file_url=file_url,
            user_id=current_user.user_id
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        return {"message": "Video uploaded successfully", "file_url": file_url}
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

@app.post("/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    user_db = authenticate_user(db, user.username, user.password)
    if not user_db:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token, jit = create_token(user_db.user_id, user_db.username)
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "jit": jit,
        "user": {
            "user_id": user_db.user_id,
            "username": user_db.username,
            "email": user_db.email
        }
    }
