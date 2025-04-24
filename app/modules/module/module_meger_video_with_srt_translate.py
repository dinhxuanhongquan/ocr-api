import os
import re
import pysrt
from datetime import timedelta

from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.VideoClip import TextClip


# Set đường dẫn ImageMagick
os.environ['IMAGEMAGICK_BINARY'] = r"C:\Program Files\ImageMagick-7.1.1-Q16\magick.exe"
font_path = r"C:\Windows\Fonts\Arial.ttf"


def srt_time_to_seconds(time_obj):
    return time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds + time_obj.milliseconds / 1000.0


import ffmpeg 
import os

def add_subtitles_to_video(video_path, subtitle_path, output_path):
    try:
        # Kiểm tra xem input và output có trùng nhau không
        if os.path.abspath(video_path) == os.path.abspath(output_path):
            # Nếu trùng, tạo một tên file tạm khác
            output_dir = os.path.dirname(output_path)
            output_filename = os.path.basename(output_path)
            temp_output_path = os.path.join(output_dir, f"temp_{output_filename}")
        
            print(f"Input và output trùng nhau. Sử dụng file tạm: {temp_output_path}")
            will_rename = True
        else:
            temp_output_path = output_path
            will_rename = False
        
        # Đảm bảo thư mục output tồn tại
        os.makedirs(os.path.dirname(temp_output_path), exist_ok=True)
        
        # Đọc input video
        video_input = ffmpeg.input(video_path)

        # tach cac luong
        video = video_input.video
        audio = video_input.audio
        
        
        # Thêm subtitles
        video_with_subs = ffmpeg.filter(video, 'subtitles', subtitle_path)
        
        # Các tham số output tối ưu hơn
        output = ffmpeg.output(
            video_with_subs, audio, 
            temp_output_path,
            acodec='copy',  # Copy audio
            vcodec='libx264',  # Re-encode video
            preset='medium',  # Thay đổi từ fast sang medium để cân bằng tốc độ/chất lượng
            crf=23,
            pix_fmt='yuv420p',  # Đảm bảo tương thích với nhiều player
            movflags='+faststart'  # Tối ưu cho streaming
        )
        
        # Chạy lệnh
        ffmpeg.run(output, overwrite_output=True)
        
        # Nếu cần, rename file tạm thành file output cuối cùng
        if will_rename:
            # Đợi để đảm bảo file đã được đóng
            import time
            time.sleep(0.5)
            
            # Xóa file gốc
            if os.path.exists(output_path):
                os.remove(output_path)
                
            # Đổi tên file tạm thành file output
            os.rename(temp_output_path, output_path)
        return True
    
    except Exception as e:
        print(f"Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return False