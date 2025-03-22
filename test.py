import json
import cv2
import boto3
from paddleocr import PaddleOCR
from moviepy.video.io.VideoFileClip import VideoFileClip
import difflib
import os

ocr = PaddleOCR(use_angle_cls=True, lang="ch")

# ===== Cấu hình MySQL =====
# DB_HOST = "db-sub-video.c1siqkqs2a46.ap-southeast-2.rds.amazonaws.com"
# DB_USER = "admin"
# DB_PASSWORD = "Abc123456"
# DB_NAME = "db_sub_video"
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME", "video-input-storge")
BUCKET_NAME_SRT = os.getenv("BUCKET_NAME_SRT", "srt-input-storage")
S3_REGION = os.getenv("S3_REGION", "ap-southeast-2")


"""
dau vao cua lambda la event av text
event la file_name

tao ra 1 file srt va lua vao bucket tai S3
"""
# CAU HINH S3
s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
)

def get_video(video_name):
    file_name = f"{video_name}.mp4"
    file_path = f"/tmp/{file_name}"
    s3.download_file(BUCKET_NAME, file_name, file_path)
    return file_path

# Hàm tính độ giống nhau giữa 2 chuỗi
def text_similarity(text1, text2):
    return difflib.SequenceMatcher(None, text1, text2).ratio()

# Hàm format timestamp kiểu SRT
def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds * 1000) % 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def export_srt(file_path):
    clip = VideoFileClip(file_path)

    #Thong so video
    fps = clip.fps
    # Ngưỡng cài đặt
    SIMILARITY_THRESHOLD = 0.8    # Text giống nhau >80% thì coi là cùng nội dung
    STABILIZATION_THRESHOLD = 0.5  # Giữ nguyên text ít nhất 0.5 giây mới ghi phụ đề mới
    MIN_TEXT_LENGTH = 3            # Bỏ qua dòng quá ngắn (noise)

    # Biến lưu phụ đề
    subtitles = []

    # Biến trạng thái
    previous_text = ""
    start_time = 0.0
    last_change_time = 0.0
        
    # Duyệt từng frame của video (FPS gốc)
    for frame_number, frame in enumerate(clip.iter_frames(fps=fps, dtype='uint8')):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # Lấy vùng phụ đề (dưới màn hình)
        h, w = gray.shape
        bottom_half = gray[int(h * 3 / 4):, :]

        # OCR lấy text
        result = ocr.ocr(bottom_half)

        if not result or not isinstance(result, list) or len(result) == 0 or not result[0]:
            continue  # Bỏ qua nếu OCR không nhận diện được text nào

        # Ghép text từ kết quả OCR
        current_text = " ".join(
            [line[1][0] for line in result[0] if line and len(line) > 1 and line[1] and line[1][0].strip()])

        # Loại bỏ text quá ngắn (chống noise OCR)
        if len(current_text.strip()) < MIN_TEXT_LENGTH:
            continue

        # Tính timestamp hiện tại (s)
        current_time = frame_number / video_fps

        # Nếu text thay đổi
        if current_text != previous_text:
            similarity = text_similarity(current_text, previous_text)

            if similarity < SIMILARITY_THRESHOLD:
                # Text khác hẳn => ghi lại đoạn cũ (nếu đủ lâu)
                if previous_text and (current_time - last_change_time > STABILIZATION_THRESHOLD):
                    subtitles.append((start_time, current_time, previous_text))

                # Reset sang đoạn mới
                start_time = current_time
                previous_text = current_text
                last_change_time = current_time
            # Nếu chỉ khác nhẹ thì bỏ qua (coi như noise nhỏ)
        # Nếu text giống nhau: không làm gì cả (đang trong cùng 1 đoạn phụ đề)

    # Kết thúc: Ghi đoạn cuối cùng (nếu còn)
    if previous_text:
        subtitles.append((start_time, clip.duration, previous_text))

    # Ghi ra file SRT
    with open('subtitles.srt', 'w', encoding='utf-8') as srt_file:
        for idx, (start, end, text) in enumerate(subtitles):
            srt_file.write(f"{idx+1}\n")
            srt_file.write(f"{format_timestamp(start)} --> {format_timestamp(end)}\n")
            srt_file.write(f"{text}\n\n")

    return 'subtitles.srt'



    


# Hàm xử lý Lambda
def lambda_handler(event, context):
    # Lấy tên file video
    video_name = event.get("video_name")
    # Lấy file video từ S3
    video_path = get_video(video_name)
    # Xử lý video
    srt_path = export_srt(video_path)
    # Upload file SRT lên S3
    s3.upload_file(srt_path, BUCKET_NAME_SRT, srt_path)
    # Xóa file SRT tạm
    os.remove(srt_path)
    # Trả kết quả
    
    return {"statusCode": 200, "body": json.dumps({"message": "Xử lý xong", "srt_file": srt_path})}
