# from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form, Request
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from fastapi.responses import JSONResponse
# from fastapi.middleware.cors import CORSMiddleware
# from starlette.middleware.sessions import SessionMiddleware
# from jose import JWTError, jwt
# from passlib.context import CryptContext
# from datetime import datetime, timedelta
# from pydantic import BaseModel, EmailStr
# import shutil
# import os
# from database import User, Video, BlackListToken,SRT, VIDEO_TTS, get_db
# from sqlalchemy.orm import Session
# import s3
# from authlib.integrations.starlette_client import OAuth
# from starlette.config import Config
# from fastapi.responses import JSONResponse
# import uuid

# app = FastAPI(title="Video Translation API")

# # Add SessionMiddleware
# app.add_middleware(
#     SessionMiddleware,
#     secret_key=os.getenv('SESSION_SECRET_KEY', 'your-secret-key-here'),
#     session_cookie="session"
# )

# # Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # OAuth2 configuration
# config = Config('.env')
# oauth = OAuth(config)

# # Load Google credentials from environment variables
# oauth.register(
#     name='google',
#     client_id=os.getenv('GOOGLE_CLIENT_ID'),
#     client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
#     server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
#     client_kwargs={
#         'scope': 'openid email profile',
#         'response_type': 'code',
#         'redirect_uri': 'http://localhost:8000/auth/google'
#     }
# )

# # Load Microsoft credentials from environment variables
# oauth.register(
#     name='microsoft',
#     client_id=os.getenv('MICROSOFT_CLIENT_ID'),
#     client_secret=os.getenv('MICROSOFT_CLIENT_SECRET'),
#     server_metadata_url='https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration',
#     client_kwargs={'scope': 'openid email profile',
#                    'validate_issuer': False}
# )

# class UserCreate(BaseModel):
#     username: str
#     email: EmailStr
#     password: str

# class UserLogin(BaseModel):
#     username: str
#     password: str

# class TokenRequest(BaseModel):
#     username: str
#     password: str


# # JWT setup
# SECRET_KEY = "/EyY1GnelIliNbL0Lempu5rEAzVZ5xQ4GWvO1dOTml0ouAA7EAmM5c84BoZPYlFi"
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30

# # OAuth2 scheme
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", scheme_name="JWT")

# # Password context
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# def verify_password(plain_password, hashed_password):
#     return pwd_context.verify(plain_password, hashed_password)

# def get_password_hash(password):
#     return pwd_context.hash(password)

# def authenticate_user(db: Session, username: str, password: str):
#     user = db.query(User).filter(User.username == username).first()
#     if not user:
#         return False
#     if not verify_password(password, user.password):
#         return False
#     return user

# def create_token(user_id: str, username: str):
#     jit = str(uuid.uuid4())  # Generate unique JIT for each login
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     data = {
#         "sub": username,
#         "uid": user_id,
#         "jit": jit,
#         "exp": expire
#     }
#     encoded_jwt = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt, jit

# async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         # Remove 'Bearer ' prefix if present
#         if token.startswith('Bearer '):
#             token = token.split(' ')[1]
            
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         user_id: str = payload.get("uid")
#         jit: str = payload.get("jit")
        
#         if not all([username, user_id, jit]):
#             raise credentials_exception
            
#         # Check if token is blacklisted
#         blacklist_token = f"BLACK_LIST_{user_id}_{jit}"
#         blacklisted = db.query(BlackListToken).filter(
#             BlackListToken.invalid_token == blacklist_token
#         ).first()
#         if blacklisted:
#             raise credentials_exception
            
#         user = db.query(User).filter(
#             User.username == username,
#             User.user_id == user_id
#         ).first()
#         if user is None:
#             raise credentials_exception
#         return user
#     except JWTError as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=f"Invalid token: {str(e)}",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=f"Authentication error: {str(e)}",
#             headers={"WWW-Authenticate": "Bearer"},
#         )




# # @app.get('/login/google')
# # async def google_login(request: Request, db: Session = Depends(get_db)):
# #     try:
# #         if "code" not in request.query_params:
# #             # Chưa có code -> Chuyển hướng đến Google để đăng nhập
# #             redirect_uri = request.url_for("google_login")
# #             return await oauth.google.authorize_redirect(request, redirect_uri)

# #         # Lấy token từ Google bằng code đã nhận
# #         token = await oauth.google.authorize_access_token(request)
# #         if not token:
# #             raise HTTPException(status_code=400, detail="Failed to get token from Google")

# #         # Lấy thông tin người dùng từ token
# #         user_info = token.get("userinfo")
# #         if not user_info or "email" not in user_info:
# #             raise HTTPException(status_code=400, detail="Failed to get user info from Google")

# #         # Kiểm tra user trong database
# #         db_user = db.query(User).filter(User.email == user_info["email"]).first()
        
# #         if not db_user:
# #             # Tạo username từ email (tránh trùng lặp bằng cách thêm UUID ngắn)
# #             username_base = user_info["email"].split("@")[0]
# #             username = username_base
# #             while db.query(User).filter(User.username == username).first():
# #                 username = f"{username_base}_{uuid.uuid4().hex[:6]}"  # Thêm 6 ký tự ngẫu nhiên
            
# #             # Tạo user mới
# #             db_user = User(
# #                 username=username,
# #                 email=user_info["email"],
# #                 password=get_password_hash(os.urandom(32).hex())  # Mật khẩu ngẫu nhiên, không sử dụng được
# #             )
# #             db.add(db_user)
# #             db.commit()
# #             db.refresh(db_user)

# #         # Tạo JWT token
# #         access_token, jit = create_token(db_user.user_id, db_user.username)

# #         # **Lưu access_token vào session**
# #         request.session["access_token"] = access_token
# #         request.session["user_info"] = {
# #             "user_id": db_user.user_id,
# #             "username": db_user.username,
# #             "email": db_user.email
# #         }

# #         return JSONResponse(content={"message": "Login successful, token saved in session"}, status_code=200)

# #     except Exception as e:
# #         raise HTTPException(status_code=400, detail=f"Google authentication failed: {str(e)}")

        
        
# # @app.get("/login/microsoft")
# # async def microsoft_login(request: Request, db: Session = Depends(get_db)):
# #     # BƯỚC 1: Chưa có ?code= => Bắt đầu đăng nhập
# #     if "code" not in request.query_params:
# #         # Tạo redirect_uri chính là route này => Authlib sinh 'state' và chuyển hướng sang Microsoft
# #         redirect_uri = request.url_for("microsoft_login")  # => http://localhost:8000/login/microsoft
# #         return await oauth.microsoft.authorize_redirect(request, redirect_uri)
# #     else:
# #         # BƯỚC 2: Microsoft đã redirect quay về kèm ?code=xxx&state=yyy => Xử lý callback
# #         try:
# #             token = await oauth.microsoft.authorize_access_token(request)
# #             if not token:
# #                 raise HTTPException(status_code=400, detail="Failed to get token from Microsoft")

# #             user_info = token.get("userinfo")
# #             if not user_info or "email" not in user_info:
# #                 raise HTTPException(status_code=400, detail="Failed to get user info from Microsoft")

# #             # Check user in DB, or create new
# #             db_user = db.query(User).filter(User.email == user_info["email"]).first()
# #             if not db_user:
# #                 username = user_info["email"].split("@")[0]
# #                 while db.query(User).filter(User.username == username).first():
# #                     username += os.urandom(2).hex()

# #                 db_user = User(
# #                     username=username,
# #                     email=user_info["email"],
# #                     password=get_password_hash(os.urandom(32).hex())
# #                 )
# #                 db.add(db_user)
# #                 db.commit()
# #                 db.refresh(db_user)

# #             # Tạo JWT
# #             access_token, jit = create_token(db_user.user_id, db_user.username)

# #             return {
# #                 "access_token": access_token,
# #                 "token_type": "bearer",
# #                 "jit": jit,
# #                 "user": {
# #                     "user_id": db_user.user_id,
# #                     "username": db_user.username,
# #                     "email": db_user.email
# #                 }
# #             }
# #         except Exception as e:
# #             raise HTTPException(
# #                 status_code=400,
# #                 detail=f"Microsoft authentication failed: {str(e)}"
# #             )



# @app.post("/register")
# async def register(user: UserCreate, db: Session = Depends(get_db)):
#     # Check if username exists
#     db_user = db.query(User).filter(User.username == user.username).first()
#     if db_user:
#         raise HTTPException(status_code=400, detail="Username already registered")
    
#     # Check if email exists
#     db_user = db.query(User).filter(User.email == user.email).first()
#     if db_user:
#         raise HTTPException(status_code=400, detail="Email already registered")
    
#     hashed_password = get_password_hash(user.password)
#     db_user = User(
#         username=user.username,
#         email=user.email,
#         password=hashed_password
#     )
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#     # return {"message": "User created successfully"}
#     return JSONResponse(
#         status_code=200,
#         content={
#             "Message": "User created successfully!"
#         }
#     )

# @app.post("/token", response_model=None)
# async def get_token(
#     form_data: OAuth2PasswordRequestForm = Depends(), 
#     db: Session = Depends(get_db)
#     ):
#     user = authenticate_user(db, form_data.username, form_data.password)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     access_token, jit = create_token(user.user_id, user.username)
#     return JSONResponse(
#         status_code=200,
#         content={
#             "Access_token": access_token
#             }
#     )

# @app.post("/login")
# async def login(
#     user: UserLogin, 
#     db: Session = Depends(get_db)
#     ):
#     user_db = authenticate_user(db, user.username, user.password)
#     if not user_db:
#         raise HTTPException(status_code=401, detail="Invalid credentials")
    
#     access_token, jit = create_token(user_db.user_id, user_db.username)
#     return JSONResponse(
#         status_code=200,
#         content={
#             "Message": "Login successful!",
#             "Access_token": access_token
#         }
#     )

# @app.post("/logout")
# async def logout(
#     request: Request, 
#     db: Session = Depends(get_db)
#     ):
#     try:
#         # Get token from authorization header
#         auth_header = request.headers.get('Authorization')
#         if not auth_header or not auth_header.startswith('Bearer '):
#             raise HTTPException(
#                 status_code=401, 
#                 detail="Invalid authorization header",
#                 headers={"WWW-Authenticate": "Bearer"}
#             )
        
#         token = auth_header.split(' ')[1]
#         try:
#             payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#             user_id = payload.get("uid")
#             jit = payload.get("jit")
            
#             if not all([user_id, jit]):
#                 raise HTTPException(
#                     status_code=401,
#                     detail="Invalid token format",
#                     headers={"WWW-Authenticate": "Bearer"}
#                 )
            
#             # Create blacklist token string
#             blacklist_token = f"BLACK_LIST_{user_id}_{jit}"
            
#             # Add to blacklist
#             db_blacklist = BlackListToken(
#                 invalid_token=blacklist_token
#             )
#             db.add(db_blacklist)
#             db.commit()
            
#             return JSONResponse(
#                 status_code=200,
#                 content={
#                     "Message": "Successfully logged out!"
#                 }
#             )
#         except JWTError as e:
#             raise HTTPException(
#                 status_code=401,
#                 detail=f"Invalid token: {str(e)}",
#                 headers={"WWW-Authenticate": "Bearer"}
#             )
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=str(e),
#             headers={"WWW-Authenticate": "Bearer"}
#         )
    

# #  Http with table video
# @app.post("/videos/upload")
# async def upload_video(
#     file: UploadFile = File(...),
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     if not file.content_type.startswith("video/"):
#         raise HTTPException(status_code=400, detail="File must be a video")

#     # Create temp directory if it doesn't exist
#     os.makedirs("temp", exist_ok=True)
    
#     temp_file = f"temp/{file.filename}"
#     try:
#         with open(temp_file, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)

#         # Upload to S3 thay doi ten cua file
#         new_filename = f"{current_user.user_id}_{file.filename}"
#         s3.s3_client.upload_file(temp_file, s3.video_input_storage, new_filename)
#         file_url = f"https://{s3.video_input_storage}.s3.amazonaws.com/{new_filename}"

#         # Save video information to database
#         video = Video(
#             file_name=file.filename,
#             file_url=file_url,
#             user_id=current_user.user_id
#         )
#         db.add(video)
#         db.commit()
#         db.refresh(video)

#         # Xoa folder temp
#         shutil.rmtree("temp")

#         # return {"message": "Video uploaded successfully", "file_url": file_url}
#         return JSONResponse(
#             status_code=200,
#             content={
#                 "Message": "Video uploaded successfully!",
#                 "File_url":file_url
#             }
#         )
#     finally:
#         if os.path.exists(temp_file):
#             os.remove(temp_file)



# #  Http with table video
# #  Lấy video theo user_id trong token
# @app.get("/videos")
# async def get_videos(
#     current_user: User = Depends(get_current_user), 
#     db: Session = Depends(get_db)
#     ):
#     videos = db.query(Video).filter(Video.user_id == current_user.user_id).all()

#     # Download video from S3 by video_name
#     # Create temp directory if it doesn't exist
#     os.makedirs("temp", exist_ok=True)
    
#     for video in videos:
#         s3.s3_client.download_file(s3.video_input_storage, video.file_name, f"temp/{video.file_name}")
#     # return all video in videos with JSONResponse
#     return JSONResponse(
#         status_code=200,
#         content={
#             "Videos": [
#                 {
#                     "user_id": video.user_id,
#                     "video_id": video.video_id,
#                     "file_name": video.file_name,
#                     "file_url": video.file_url
#                 } for video in videos
#             ]
#         }
#     )

# # Get video by video_name
# @app.get("/videos/{video_id}")
# async def get_video(
#     video_id: str, 
#     current_user: User = Depends(get_current_user), 
#     db: Session = Depends(get_db)
#     ):
#     video = db.query(Video).filter(Video.video_id == video_id).first()
#     # Download video from S3 by video_name
#     # Create temp directory if it doesn't exist
#     os.makedirs("temp", exist_ok=True)
#     s3.s3_client.download_file(s3.video_input_storage, video.file_name, f"temp/{video.file_name}")
#     return JSONResponse(
#         status_code=200,
#         content={
#             "Message": "Video downloaded successfully!"
#         }
#     )

# @app.delete("/videos/{video_id}")
# async def delete_video(
#     video_id: str, 
#     current_user: 
#     User = Depends(get_current_user), 
#     db: Session = Depends(get_db)
#     ):
#     video = db.query(Video).filter(Video.video_id == video_id).first()
#     if video.user_id != current_user.user_id:
#         raise HTTPException(
#             status_code=403, 
#             detail="You don't have permission to delete this video"
#             )
#     # Delete video from S3
#     s3.s3_client.delete_object(
#         Bucket=s3.video_input_storage, 
#         Key=video.file_url.split("/")[-1]
#         )
#     # Delete video from database
#     db.delete(video)
#     db.commit()
#     return JSONResponse(
#         status_code=200,
#         content={
#             "Message": "Video deleted successfully!"
#         }
#     )



# # Post srt
# @app.post("/srt/upload/{video_id}")
# async def upload_srt(
#     video_id: str,
#     file_srt: UploadFile = File(...),
#     file_srt_sub: UploadFile = File(...),
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     if not (file_srt.content_type == "text/plain" and file_srt_sub.content_type == "text/plain"):
#         raise HTTPException(status_code=400, detail="File must be a srt file")

#     # Create temp directory if it doesn't exist
#     os.makedirs("temp", exist_ok=True)
    
#     temp_file = f"temp/{file_srt.filename}"
#     temp_file_sub = f"temp/{file_srt_sub.filename}"
#     try:
#         with open(temp_file, "wb") as buffer:
#             shutil.copyfileobj(file_srt.file, buffer)

#         # Upload to S3
#         new_filename_srt = f"{current_user.user_id}_{video_id}_{file_srt.filename}"
#         new_filename_sub = f"{current_user.user_id}_{video_id}_{file_srt_sub.filename}"
#         s3.s3_client.upload_file(temp_file, s3.video_input_storage, new_filename_srt)
#         s3.s3_client.upload_file(temp_file_sub, s3.video_input_storage, new_filename_sub)
#         srt_url = f"https://{s3.video_input_storage}.s3.amazonaws.com/{new_filename_srt}"
#         srt_url_sub = f"https://{s3.video_input_storage}.s3.amazonaws.com/{new_filename_sub}"

#         # Save srt information to database
#         srt = SRT(
#             video_id=video_id,
#             srt_name=file_srt.filename,
#             srt_url=srt_url,
#             srt_url_sub=srt_url_sub
#         )
#         db.add(srt)
#         db.commit()
#         db.refresh(srt)

#         # Xoa folder temp
#         shutil.rmtree("temp")

#         # return {"message": "SRT uploaded successfully", "file_url": srt_url}
#         return JSONResponse(
#             status_code=200,
#             content={
#                 "Message": "SRT uploaded successfully!",
#                 "File_url": srt_url
#             }
#         )
#     finally:
#         if os.path.exists(temp_file):
#             os.remove(temp_file)

# # Get file srt by video_name
# @app.get("/srt/{video_id}")
# async def get_srts(
#     video_id: str,
#     current_user: User = Depends(get_current_user), 
#     db: Session = Depends(get_db)
#     ):
#     # Lay tat ca
#     srts = db.query(SRT).filter(SRT.video_id == video_id).all()
#     return JSONResponse(
#         status_code=200,
#         content={
#             "SRTs": [srt.srt_name for srt in srts],
#             "URL": [srt.srt_url for srt in srts],
#             "URL_SUB": [srt.srt_url_sub for srt in srts]
#         }
#     )

# @app.delete("srt/{srt_id}")
# async def delete_srt(
#     srt_id: str, 
#     db: Session = Depends(get_db)
#     ):
#     srt = db.query(SRT).filter(SRT.srt_id == srt_id).first()

#     srt_url = srt.srt_url
#     srt_sub_url = srt.srt_url_sub
#     # Delete srt from S3
#     s3.s3_client.delete_object(Bucket=s3.video_input_storage, Key=srt_url.split("/")[-1])
#     s3.s3_client.delete_object(Bucket=s3.video_input_storage, Key=srt_sub_url.split("/")[-1])
#     # Delete srt from database
#     db.delete(srt)
#     db.commit()
#     return JSONResponse(
#         status_code=200,
#         content={
#             "Message": "SRT deleted successfully!"
#         }
#     )

import uvicorn
from app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="localhost", port=8000, reload=True)