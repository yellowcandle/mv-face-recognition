import yt_dlp
import os
import subprocess
import logging
from rich.logging import RichHandler
from argparse import ArgumentParser

# List of videos to download
url_list = {
    "v1": "https://www.youtube.com/watch?v=IpuMy0PcPAE",
    "v2": "https://www.youtube.com/watch?v=2thpVqZsKHA",
    "v3": "https://www.youtube.com/watch?v=O8MOUs0sz4U",
    "v4": "https://www.youtube.com/watch?v=gizlTwFUL1M",
    "v5": "https://www.youtube.com/watch?v=cTtBqzGI-HM",
    "v6": "https://www.youtube.com/watch?v=3oreuR2L2GA",
}

download_dir = "./source/videos"  # Directory to store downloaded videos
os.makedirs(download_dir, exist_ok=True)  # Ensure the directory exists

logger = logging.getLogger(__name__)

def setup_logging(level):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler()]
    )

def download_video(url, output_path):
    ydl_opts = {
        "outtmpl": output_path + ".%(ext)s",
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",  # This will select the best video quality with highest bitrate
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    output_file = output_path + ".mp4"

def main():
    parser = ArgumentParser()
    parser.add_argument('-v','--verbose', action='store_true', help='Verbose logs')
    parser.add_argument('--log-level', choices=['DEBUG','INFO','WARNING','ERROR'], help='Set log level')
    args = parser.parse_args()
    level = logging.INFO
    if args.log_level:
        level = getattr(logging, args.log_level)
    elif args.verbose:
        level = logging.DEBUG
    setup_logging(level)
    logger.info("Starting video downloads...")
    for key, url in url_list.items():
        output_path = os.path.join(download_dir, key)
        logger.info("Downloading %s from %s", key, url)
        download_video(url, output_path)
        logger.success("Downloaded %s", key)

if __name__ == '__main__':
    main()
