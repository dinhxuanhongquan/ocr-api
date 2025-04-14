# sư dụng python:3.12 làm base 
FROM python:3.12

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Cài đặt các dependencies hệ thống
RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    libmagickwand-dev \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục làm việc
WORKDIR /app

# Copy requirements.txt
COPY requirements.txt .

# Cài đặt Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code
COPY . .

# Tạo các thư mục cần thiết
RUN mkdir -p tempvideo tempsrt tempaudio temp_thumbnails temp_processing

# Cấu hình ImageMagick
ENV IMAGEMAGICK_BINARY=/usr/bin/convert

# Expose port
EXPOSE 8000

# Command để chạy ứng dụng
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 