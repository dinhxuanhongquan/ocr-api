import os
import re
import pysrt
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.VideoClip import TextClip, ColorClip

# Set đường dẫn ImageMagick
os.environ['IMAGEMAGICK_BINARY'] = r"C:\Program Files\ImageMagick-7.1.1-Q16\magick.exe"
font_path = r"C:\Windows\Fonts\Arial.ttf"


def srt_time_to_seconds(time_obj):
    """Chuyển đổi thời gian từ pysrt.SubRipTime sang giây."""
    return time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds + time_obj.milliseconds / 1000.0

def add_subtitles_to_video(video_path, srt_path, output_path):
    """Ghép phụ đề vào video."""
    video = VideoFileClip(video_path)
    subs = pysrt.open(srt_path)
    subtitle_clips = []

    for sub in subs:
        txt_clip = (TextClip(
                        text = sub.text, font_size=40, color='yellow', bg_color='black', font=font_path,
                        size=(video.w - 100, None), method="caption")  # Giới hạn chiều rộng phụ đề
                    .with_position(('center', 'bottom'))
                    .with_start(srt_time_to_seconds(sub.start))
                    .with_duration(srt_time_to_seconds(sub.end) - srt_time_to_seconds(sub.start)))
        subtitle_clips.append(txt_clip)

    final_video = CompositeVideoClip([video] + subtitle_clips)
    final_video.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=video.fps)

    