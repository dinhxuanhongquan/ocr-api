import pysrt
import os
import ffmpeg
import re
import edge_tts
import asyncio
import tempfile
import shutil

def srt_time_to_milliseconds(srt_time):
    return (srt_time.hours * 3600 + srt_time.minutes * 60 + srt_time.seconds) * 1000 + srt_time.milliseconds

def normalize_text(text):
    text = text.strip()
    text = re.sub(r'([.,!?])([^\s])', r'\1 \2', text)
    return text

def detect_language(text):
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    return 'vi'

def calculate_rate(text, duration_ms):
    base_duration = len(text) * 100
    rate = (base_duration / duration_ms) * 100
    rate = max(50, min(rate, 200))
    return f"+{int(rate)}%"

async def text_to_speech(text, output_path, duration_ms, voice):
    try:
        text = normalize_text(text)
        rate = calculate_rate(text, duration_ms)
        
        if detect_language(text) == 'zh':
            voice = "zh-CN-XiaoxiaoNeural"
        
        temp_audio = output_path + "_temp.mp3"
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(temp_audio)
        await asyncio.sleep(1)

        if not os.path.exists(temp_audio):
            raise Exception("Không nhận được file audio. Kiểm tra tham số API.")
        
        os.rename(temp_audio, output_path)
        return True
    except Exception as e:
        print(f"Lỗi khi tạo audio: {str(e)}")
        return False

def merge_audio_files(audio_files, output_file):
    with open("file_list.txt", "w", encoding="utf-8") as f:
        for file in audio_files:
            f.write(f"file '{file}'\n")
    
    ffmpeg.input("file_list.txt", format="concat", safe=0)\
        .output(output_file, c="copy")\
        .run(overwrite_output=True)
    os.remove("file_list.txt")


def generate_audio_from_srt(srt_file, save_dir, voice):
    """
    Tạo file audio từ file SRT bằng Edge TTS.
    Trả về đường dẫn file đã tạo (trong `save_dir`), hoặc `None` nếu thất bại.
    """
    voice = "vi-VN-NamMinhNeural" if voice == "2" else "vi-VN-HoaiMyNeural"  # 🔹 Chọn giọng nói

    if not os.path.exists(srt_file):
        print("File phụ đề không tồn tại!")
        return None

    subs = pysrt.open(srt_file, encoding="utf-8")
    temp_dir = tempfile.mkdtemp()
    temp_files = []

    output_audio_file = os.path.join(save_dir, f"{os.path.basename(srt_file).split('.')[0]}.mp3")
    
    async def process_all():
        for sub in subs:
            start_ms = srt_time_to_milliseconds(sub.start)
            end_ms = srt_time_to_milliseconds(sub.end)
            duration = end_ms - start_ms
            temp_filename = os.path.join(temp_dir, f"temp_{start_ms}.mp3")
            success = await text_to_speech(sub.text, temp_filename, duration, voice)

            if success:
                temp_files.append(temp_filename)
            else:
                print(f"Lỗi khi tạo audio cho đoạn: {sub.text}")
        
        if temp_files:
            print(f"Đang ghép {len(temp_files)} file audio lại thành {output_audio_file}...")
            merge_audio_files(temp_files, output_audio_file)

            # Kiểm tra file cuối cùng có tồn tại không
            if os.path.exists(output_audio_file):
                print(f"Đã tạo file audio hoàn chỉnh: {output_audio_file}")
            else:
                print("File audio cuối cùng không tồn tại!")
                return None
            
            # Xóa file tạm
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

            shutil.rmtree(temp_dir)
            return output_audio_file
        return None

    # Sử dụng event loop hiện tại thay vì tạo mới với asyncio.run()
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(process_all())
    except RuntimeError:
        # Nếu không có event loop (trường hợp gọi trực tiếp)
        return asyncio.run(process_all())

    # return output_audio_file  # 🔹 Trả về đường dẫn file trong `save_dir`
