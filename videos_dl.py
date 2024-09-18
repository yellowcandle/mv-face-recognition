import yt_dlp

url_list = {'v1':'https://www.youtube.com/watch?v=IpuMy0PcPAE', 'v2': 'https://www.youtube.com/watch?v=2thpVqZsKHA', 'v3': 'https://www.youtube.com/watch?v=O8MOUs0sz4U'}

def download_video(url, output_path):
    ydl_opts = {
        'outtmpl': output_path + '.%(ext)s',
        'format': 'best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

for video_id, url in url_list.items():
    output_path = f'/source/videos/{video_id}'
    download_video(url, output_path)
