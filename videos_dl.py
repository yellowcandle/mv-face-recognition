import yt_dlp
import os
import subprocess

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
        'format': 'best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    # Automatically add and commit the downloaded video to Git
    subprocess.run(["git", "commit", "-m", f"Add video {output_path}.mp4"])
    subprocess.run(["git", "add", output_path + ".mp4"])

for video_id, url in url_list.items():
    output_path = os.path.join(download_dir, video_id)
    download_video(url, output_path)
