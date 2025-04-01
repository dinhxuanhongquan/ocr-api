import time
import pysrt
import difflib
import cv2
import re
from moviepy.video.io.VideoFileClip import VideoFileClip
from paddleocr import PaddleOCR
import google.generativeai as genai
import ffmpeg
import boto3
import os
from app.core.config import get_settings
from app.modules.s3_process import download_file_from_s3, upload_file_to_s3, delete_file_from_s3, replace_file_on_s3
from app.modules.module.module_text_to_speech_v2 import generate_audio_from_srt
from app.modules.module.module_meger_video_v2 import process_video_with_sync
from app.modules.module.module_meger_video_with_srt_translate import add_subtitles_to_video



# Cấu hình API Gemini
genai.configure(api_key=get_settings().API_KEY)
model = genai.GenerativeModel(get_settings().API_MODEL)



ocr = PaddleOCR(lang='ch')

def format_timestamp(seconds):
    """Chuyển đổi giây thành định dạng SRT (hh:mm:ss,ms)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds * 1000) % 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def extract_subtitles(video_path, output_srt):
    clip = VideoFileClip(video_path)
    try:
        fps = clip.fps
        subtitles = []
        prev_text = ""
        start_time = 0.0
        min_length = 3
        similarity_threshold = 0.8
        frame_skip = 5  # Bỏ qua 5 frame để tối ưu OCR

        # Create tempsrt directory if it doesn't exist
        os.makedirs("tempsrt", exist_ok=True)
        
        # Tao ten moi cho file output
        base_name = os.path.splitext(os.path.basename(output_srt))[0]
        counter = 1
        temp_srt = output_srt
        while os.path.exists(os.path.join("tempsrt", temp_srt)):
            temp_srt = f"{counter}_{base_name}.srt"
            counter += 1

        # Create temporary file in current directory
        temp_file = "temp_" + temp_srt
        final_path = os.path.join("tempsrt", temp_srt)
        
        with open(temp_file, 'w', encoding='utf-8') as srt_file:
            for frame_number, frame in enumerate(clip.iter_frames(fps=fps, dtype='uint8')):
                if frame_number % frame_skip != 0:
                    continue
                
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                h, w = gray.shape
                bottom_half = gray[int(h * 3 / 4):, :]
                result = ocr.ocr(bottom_half)
                
                current_text = " ".join([line[1][0] for line in result[0] if len(line) > 1 and line[1][0].strip()]) if result and result[0] else ""
                
                if len(current_text) < min_length:
                    continue
                
                current_time = frame_number / fps
                
                if difflib.SequenceMatcher(None, current_text, prev_text).ratio() < similarity_threshold:
                    if prev_text:
                        subtitles.append((format_timestamp(start_time), format_timestamp(current_time), prev_text))
                    start_time = current_time
                    prev_text = current_text

            if prev_text:
                subtitles.append((format_timestamp(start_time), format_timestamp(clip.duration), prev_text))

            for i, (start, end, text) in enumerate(subtitles):
                srt_file.write(f"{i + 1}\n")
                srt_file.write(f"{start} --> {end}\n")
                srt_file.write(f"{text}\n\n")

        # Ensure temp file exists before moving
        if os.path.exists(temp_file):
            # Move file to tempsrt directory
            os.rename(temp_file, final_path)
            return final_path
        else:
            raise Exception("Failed to create subtitle file")

    finally:
        clip.close()

def batch_translate_text(text_list):
    """Gửi toàn bộ danh sách phụ đề lên API dịch một lần, giữ nguyên số thứ tự"""
    if not text_list:
        return text_list

    formatted_text = "\n".join(f"{i+1}. {text}" for i, text in enumerate(text_list))

    prompt = f"""Dịch các câu sau sang tiếng Việt, giữ nguyên số thứ tự.
                    Nếu không dịch được, hãy giữ nguyên nội dung gốc. Chỉ trả về phần dịch, không bao gồm câu gốc.

    
    {formatted_text}"""

    try:
        response = model.generate_content(prompt)
        translated_lines = response.text.strip().split("\n")

        # Xử lý kết quả trả về
        translated_dict = {}
        for line in translated_lines:
            match = re.match(r"(\d+)\.\s*(.*)", line)
            if match:
                index, translated_text = int(match.group(1)), match.group(2)
                translated_dict[index] = translated_text

        # Khớp nội dung dịch với thứ tự ban đầu
        translated_texts = [translated_dict.get(i+1, text_list[i]) for i in range(len(text_list))]

    except Exception as e:
        print(f"Lỗi dịch: {e}")
        translated_texts = text_list  # Nếu lỗi thì giữ nguyên bản gốc

    return translated_texts


def translate_srt(input_srt, output_srt):
    """Dịch file SRT bằng cách gửi toàn bộ nội dung lên API một lần"""
    try:
        # Create tempsrt directory if it doesn't exist
        os.makedirs("tempsrt", exist_ok=True)
        
        # Generate unique filename
        base_name = os.path.splitext(os.path.basename(output_srt))[0]
        counter = 1
        temp_srt = output_srt
        while os.path.exists(os.path.join("tempsrt", temp_srt)):
            temp_srt = f"{counter}_{base_name}.srt"
            counter += 1
        
        # Read and translate subtitles
        subs = pysrt.open(input_srt, encoding='utf-8')
        texts_to_translate = [sub.text for sub in subs]
        translated_texts = batch_translate_text(texts_to_translate)

        # Write translated subtitles to temporary file
        with open(temp_srt, 'w', encoding='utf-8') as srt_file:
            for i, sub in enumerate(subs):
                srt_file.write(f"{sub.index}\n")
                srt_file.write(f"{sub.start} --> {sub.end}\n")
                srt_file.write(f"{translated_texts[i]}\n\n")

        # Move file to tempsrt directory if it exists
        if os.path.exists(temp_srt):
            os.rename(temp_srt, output_srt)
            return output_srt
        else:
            raise Exception("Failed to create translated subtitle file")
            
    except Exception as e:
        print(f"Error in translate_srt: {e}")
        raise


def compress_file(video_path: str, output_path: str, crf: int = 23, preset: str = 'fast') -> bool:
    try:
        # Tạo thư mục output nếu chưa tồn tại
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        #  Tao ten mới cho file output
        basename, ext = os.path.splitext(os.path.basename(output_path))
        new_filename = basename + "_compressed" + ext
        output_path = os.path.join(os.path.dirname(output_path), new_filename)
        
        # Cấu hình ffmpeg
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(
            stream,
            output_path,
            vcodec='libx264',      # Codec video
            acodec='aac',          # Codec audio
            crf=crf,               # Chất lượng video
            preset=preset,         # Tốc độ nén
            movflags='+faststart', # Tối ưu cho streaming
            threads=0,             # Sử dụng tất cả CPU cores
            **{'b:v': '2M'}        # Bitrate video
        )
        
        # Chạy ffmpeg
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        return True
    except ffmpeg.Error:
        return False
    except Exception:
        return False


def uncompressed_file(video_path: str, output_path: str) -> bool:
    try:
        # Tạo thư mục output nếu chưa tồn tại
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        #  Tao ten mới cho file output
        basename, ext = os.path.splitext(os.path.basename(output_path))
        new_filename = basename + "_uncompressed" + ext
        output_path = os.path.join(os.path.dirname(output_path), new_filename)
        
        # Cấu hình ffmpeg
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(
            stream,
            output_path,
            vcodec='copy',      # Codec video
            acodec='copy',      # Codec audio
            **{'b:v': '2M'}     # Bitrate video
        )
        
        # Chạy ffmpeg
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        return True
    except ffmpeg.Error:
        return False
    except Exception:
        return False
    

def tts_and_process_video(voice_choice, selected_video):

    voice = "vi-VN-NamMinhNeural" if voice_choice == "2" else "vi-VN-HoaiMyNeural"

    #  Duong dan luu video va phu de da sub
    local_video_path = os.path.join("tempvideo", selected_video['file_name'])
    local_subtitle_path = os.path.join("tempsrt", f"{selected_video['file_name'].split('.')[0]}.srt")

    # Tạo TTS từ phụ đề đã sub
    os.makedirs("tempsound", exist_ok=True)

    tts_audio_path = os.path.join("tempsound", f"tts_audio_{selected_video['video_id']}.mp3")
    tts_audio_path = generate_audio_from_srt(local_subtitle_path, "tempvideo", voice)

    if not tts_audio_path or not os.path.exists(tts_audio_path):
        print(f"Không thể tạo âm thanh từ phụ đề, file không tồn tại: {tts_audio_path}")
        return

    # Đường dẫn cho các file xử lý video
    adjusted_audio_path = os.path.join("tempvideo", f"adjusted_audio_{selected_video['video_id']}.mp3")
    output_srt_path = os.path.join("tempvideo", f"adjusted_{selected_video['video_id']}.srt")
    final_video_path = os.path.join("tempvideo", f"final_{selected_video['file_name']}")

    # Ghép âm thanh vào video
    process_video_with_sync(
        audio_file=tts_audio_path,  # File TTS gốc
        video_file=local_video_path,
        srt_file=local_subtitle_path,
        output_audio=adjusted_audio_path,
        output_srt=output_srt_path,
        output_video=final_video_path
    )

    if not os.path.exists(final_video_path):
        print(f"Không thể xử lý video: {final_video_path}")
        return

    # Tải video đã xử lý lên S3 bucket `video-sub`
    processed_filename = os.path.basename(final_video_path)
    processed_s3_url = upload_file_to_s3(final_video_path, get_settings().AWS_BUCKET_TEST , processed_filename)

    # Xóa các file tạm
    os.remove(tts_audio_path)
    os.remove(adjusted_audio_path)  
    os.remove(output_srt_path)
    os.remove(final_video_path)

    return processed_s3_url

