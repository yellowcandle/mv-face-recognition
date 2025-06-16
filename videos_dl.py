import yt_dlp
import os
import logging
import warnings
from rich.logging import RichHandler
from argparse import ArgumentParser

# Suppress fsspec warnings
warnings.filterwarnings("ignore", message=".*fsspec.*is yanked.*")

# List of videos to download
url_list = {
    "1.《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅": "https://youtu.be/IpuMy0PcPAE?si=54EeV1wjap1IkEeW",
    "2.《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅": "https://youtu.be/2thpVqZsKHA?si=Vam2rSjE8sGh2cde",
    "3.《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅": "https://youtu.be/O8MOUs0sz4U?si=nzdA3CcE10TKcykb",
    "4.《全民造星IV》極限拍MV": "https://youtu.be/gizlTwFUL1M?si=H_ozM3ixzzg77JUp",
}

download_dir = "./source/videos"  # Directory to store downloaded videos
os.makedirs(download_dir, exist_ok=True)  # Ensure the directory exists

logger = logging.getLogger(__name__)


def setup_logging(level):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler()],
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
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set log level",
    )
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
        logger.info("✅ Downloaded %s", key)


if __name__ == "__main__":
    main()
