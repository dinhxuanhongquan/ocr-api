# OCR-API

OCR-API là một RESTful API giúp xử lý video, trích xuất và dịch phụ đề, chèn phụ đề vào video và tạo audio từ phụ đề sử dụng công nghệ Text-to-Speech.

## Tính năng chính

- Tải lên video và tự động trích xuất phụ đề
- Dịch phụ đề sang ngôn ngữ khác
- Chèn phụ đề vào video
- Tạo audio từ phụ đề sử dụng Edge TTS
- Đồng bộ hóa audio với video và phụ đề
- Lưu trữ và quản lý video, phụ đề và audio trên AWS S3

## Cài đặt

### Yêu cầu hệ thống

- Python 3.8+
- FFmpeg
- ImageMagick
- MySQL/MariaDB

### Cài đặt dependencies

1. Clone repository:

```bash
git clone https://github.com/yourusername/OCR-API.git
cd OCR-API
```

2. Tạo và kích hoạt môi trường ảo:

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Cài đặt các packages:

```bash
pip install -r requirements.txt
```

4. Cấu hình file `.env`:

```
# Database Configuration
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/db_sub_video

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_BUCKET_TEST=your_bucket_name
AWS_REGION=your_aws_region

# JWT Configuration
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

5. Khởi tạo database:

```sql
CREATE DATABASE IF NOT EXISTS db_sub_video
CHARACTER SET utf8mb4
COLLATE utf8mb4_0900_ai_ci;
```

6. Chạy ứng dụng:

```bash
uvicorn app.main:app --reload
```

## Cấu trúc dự án

```
app/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   ├── auth.py
│       │   ├── users.py
│       │   └── video.py
│       └── api.py
├── core/
│   ├── config.py
│   ├── database.py
│   └── security.py
├── models/
│   ├── user.py
│   └── video.py
├── modules/
│   ├── module/
|   |___|__ module_export_video.py
│   │   ├── module_meger_video_with_srt_translate.py
│   │   ├── module_text_to_speech_v2.py
│   │   └── module_process_with_video_sync.py
│   ├── s3_process.py
│   └── video_process.py
├── schemas/
│   ├── token.py
│   ├── user.py
│   └── video.py
├── service/
│   ├── user_service.py
│   └── video_service.py
└── main.py
```

## API Endpoints

### Auth

- `POST /api/v1/auth/login`: Đăng nhập và lấy token
- `POST /api/v1/auth/register`: Đăng ký tài khoản mới

### User

- `GET /api/v1/users/me`: Lấy thông tin người dùng hiện tại
- `PUT /api/v1/users/me`: Cập nhật thông tin người dùng

### Video

- `POST /api/v1/videos/upload`: Tải lên video đồng thời sẽ tạo ra 2 file srt(dubtitle.srt và tranlate.srt)
- `POST /api/v1/videos/subtitles/{video_id}`: Tạo ra video_subtitle đồng thời chèn vào video gốc.

- `GET /api/v1/videos`: Lấy danh sách video của người dùng duoi dang preview

- `GET /api/v1/videos/{video_id}`: Lấy file video

- `GET /api/v1/videos/videotts/{video_tts_id}`: Lấy file videotts co thể thay cái này với export

- `GET /api/v1/videos/videottes/{video_id}`: Lấy danh sách videoTTS theo video id gốc được upload lên dưới dạnh preview

- `DELETE /api/v1/videos/{video_id}`: Xóa video đồng thời sẽ xóa tất cả những gì lến quan đến video đó.

- `POST /api/v1/videos/videotts/export/{video_tts_id}`: Lấy video tts theo khung hình 9:16, anh Sỹ chỉ biết làm vậy thôi nên e cũng bó tay nhưng nó lỏ lắm đừng dùng

### Subtitle

- `GET /api/v1/videos/srt/{video_id}/original`: Lấy srt chưa dịch
- `GET /api/v1/video/srt/{video_id}/translated`: Lấy srt đã dịch

### VIDEO TTS

- `POST /api/v1/videos/creation/{video_id}/{voice}`:Tạo video tts với audio TTS (voice có 2 giá trị cố định là 1 hoặc 2)

## Cấu hình

### ImageMagick

Đảm bảo ImageMagick được cài đặt và cấu hình trong biến môi trường:

```python
os.environ['IMAGEMAGICK_BINARY'] = r"C:\Program Files\ImageMagick-7.1.1-Q16\magick.exe"
```

### FFmpeg

FFmpeg cần được cài đặt và thêm vào PATH hệ thống.

### AWS S3

Cấu hình thông tin kết nối AWS S3 trong file `.env`.

## Yêu cầu nâng cao

### Tối ưu hóa

- Sử dụng multi-threading khi xử lý video
- Cấu hình codec tối ưu cho video output
- Xử lý đồng bộ audio với phụ đề

### Xử lý lỗi

- Kiểm tra tính hợp lệ của video và file SRT
- Thử chuyển đổi định dạng nếu không đọc được video
- Xử lý encoding của file SRT

## License

MIT
