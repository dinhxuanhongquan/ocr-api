import pysrt
import subprocess
import os
from moviepy.video.io.VideoFileClip import VideoFileClip, AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.VideoClip import TextClip, ColorClip


os.environ['IMAGEMAGICK_BINARY'] = r"C:\Program Files\ImageMagick-7.1.1-Q16\magick.exe"
# font_path = r"C:\Windows\Fonts\Arial.ttf"
font_path = os.environ.get('FONT_PATH', r"C:\Windows\Fonts\Arial.ttf")

def srt_time_to_seconds(time_obj):
    return time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second + time_obj.microsecond / 1e6

def process_video_with_sync(audio_file, video_file, srt_file, output_audio, output_srt, output_video):
    video = VideoFileClip(video_file)
    video_duration = video.duration
    
    result = subprocess.run(
        ["ffprobe", "-i", audio_file, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"],
        capture_output=True, text=True
    )
    audio_duration = float(result.stdout.strip())
    
    if video_duration <= 0 or audio_duration <= 0:
        print("Lỗi: Video hoặc Audio có độ dài không hợp lệ!")
        return
    
    speed_factor = audio_duration / video_duration  
    
    atempo_filter = []
    while speed_factor > 2.0:
        atempo_filter.append("atempo=2.0")
        speed_factor /= 2
    while speed_factor < 0.5:
        atempo_filter.append("atempo=0.5")
        speed_factor *= 2
    atempo_filter.append(f"atempo={speed_factor:.3f}")
    atempo_filter = ",".join(atempo_filter)
    
    subprocess.run(["ffmpeg", "-i", audio_file, "-filter:a", atempo_filter, "-vn", output_audio, "-y"])
    print(f"Đã điều chỉnh âm thanh: {output_audio}")
    
    subs = pysrt.open(srt_file, encoding="utf-8")
    original_end = srt_time_to_seconds(subs[-1].end.to_time())
    correction_factor = video_duration / original_end
    
    for sub in subs:
        new_start = srt_time_to_seconds(sub.start.to_time()) * correction_factor
        new_end = srt_time_to_seconds(sub.end.to_time()) * correction_factor
        sub.start = pysrt.SubRipTime(seconds=int(new_start), milliseconds=int((new_start % 1) * 1000))
        sub.end = pysrt.SubRipTime(seconds=int(new_end), milliseconds=int((new_end % 1) * 1000))

    
    subs.save(output_srt, encoding="utf-8")
    print(f"Đã điều chỉnh phụ đề: {output_srt}")
    
    audio = AudioFileClip(output_audio)
    w, h = video.size
    video = video.with_audio(audio)
    
    black_bar = ColorClip(size=(w, 100), color=(0, 0, 0), duration=video.duration)
    black_bar = black_bar.with_position(("center", h - 100))
    
    sub_clips = []
    for sub in subs:
        start_time = srt_time_to_seconds(sub.start.to_time())
        duration = srt_time_to_seconds(sub.end.to_time()) - start_time
        txt_clip = TextClip(
            text = sub.text, font_size=35, color='yellow', font=font_path,
            size=(w - 100, None), method='caption', bg_color="black"
        ).with_start(start_time).with_duration(duration).with_position(('center', h - 120))
        sub_clips.append(txt_clip)
    
    final_clip = CompositeVideoClip([video, black_bar] + sub_clips)
    final_clip.write_videofile(output_video, fps=24, codec="libx264", audio_codec="aac")

