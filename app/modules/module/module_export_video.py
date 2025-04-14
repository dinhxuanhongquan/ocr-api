import subprocess
import os

def export_final_video(input_path):
    # Tách file đầu vào từ path đầy đủ
    input_file = os.path.abspath(input_path)
    if not os.path.exists(input_file):
        return False

    # Tỷ lệ 9:16 cho các độ phân giải khác nhau
    aspect_ratios = {
        "480": (540, 960),    # 9:16 cho 480p
        "720": (720, 1280),   # 9:16 cho 720p
        "1080": (1080, 1920), # 9:16 cho 1080p
        "1440": (1440, 2560)  # 9:16 cho 1440p
    }

    # Mặc định 1080p
    chosen_res = "1080"
    width, height = aspect_ratios[chosen_res]

    # Đặt tên file đầu ra
    filename = os.path.splitext(os.path.basename(input_file))[0]
    output_file = f"{filename}_{width}x{height}.mp4"

    # Lệnh ffmpeg với scale để fit vừa khung hình tỷ lệ 9:16
    cmd = [
        "ffmpeg",
        "-i", input_file,
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_file
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"\n File đã lưu thành công: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Lỗi khi xử lý video: {e}")
        return False
