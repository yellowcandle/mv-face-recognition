import yt_dlp
import os
import subprocess
import ffmpeg
import platform

# List of videos to download
url_list = {
    'v1': 'https://www.youtube.com/watch?v=IpuMy0PcPAE',
    'v2': 'https://www.youtube.com/watch?v=2thpVqZsKHA',
    'v3': 'https://www.youtube.com/watch?v=O8MOUs0sz4U'
}

download_dir = './source/videos'  # Directory to store downloaded videos
os.makedirs(download_dir, exist_ok=True)  # Ensure the directory exists

def download_video(url, output_path):
    ydl_opts = {
        'outtmpl': output_path + '.%(ext)s',
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # This will select the best video quality with highest bitrate
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    output_file = output_path + '.mp4'
    
    # Automatically add and commit the downloaded video to Git
    subprocess.run(["git", "add", output_file])
    subprocess.run(["git", "commit", "-m", f"Add video {output_file}"])

for video_id, url in url_list.items():
    output_path = os.path.join(download_dir, video_id)
    download_video(url, output_path)
