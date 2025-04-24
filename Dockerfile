# Sử dụng Python 3.12 làm base image
FROM python:3.12

# Thiết lập các biến môi trường cơ bản
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Cài đặt các gói hệ thống cần thiết
RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    libmagickwand-dev \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục làm việc
WORKDIR /app

# Copy file requirements.txt trước để cache việc cài dependencies
COPY requirements.txt .

# Cài đặt các gói Python
RUN pip install --no-cache-dir -r requirements.txt

# Tạo thư mục fonts và copy font Arial từ context
RUN mkdir -p /usr/share/fonts/truetype/arial
COPY ./fonts/arial.ttf /usr/share/fonts/truetype/arial/

# Làm mới cache font
RUN fc-cache -fv

# Thiết lập biến môi trường cho font
ENV FONT_PATH=/usr/share/fonts/truetype/arial/arial.ttf

# Copy toàn bộ mã nguồn ứng dụng vào container
COPY . .

# Tạo các thư mục tạm cần thiết cho xử lý video và phụ đề
RUN mkdir -p tempvideo tempsrt tempaudio temp_thumbnails temp_processing

# Cấu hình ImageMagick
ENV IMAGEMAGICK_BINARY=/usr/bin/convert

# Mở cổng dịch vụ
EXPOSE 8000

# Command mặc định khi container khởi động
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
