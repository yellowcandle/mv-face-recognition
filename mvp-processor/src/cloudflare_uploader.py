"""
Cloudflare Upload Module
Handles uploading processed videos and metadata to Cloudflare R2 and KV storage
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class CloudflareUploader:
    """Handles uploads to Cloudflare R2 and KV storage"""

    def __init__(self, config: dict):
        self.config = config
        self.cf_config = config["cloudflare"]
        self.bucket_name = self.cf_config["r2_bucket"]

        # Initialize API client for KV
        self.api_token = self.cf_config["api_token"]
        self.account_id = self.cf_config["account_id"]

        # Initialize R2 client (may be None if credentials are missing)
        self.r2_client = None
        try:
            self.r2_client = self._initialize_r2_client()
        except Exception as e:
            logger.warning("Cloudflare R2 client initialization failed: %s", e)
            logger.warning("Continuing in local-only mode")

    def _initialize_r2_client(self):
        """Initialize Cloudflare R2 client using S3-compatible API"""
        try:
            import boto3
            from botocore.config import Config

            # R2 uses S3-compatible API
            client = boto3.client(
                "s3",
                endpoint_url=self.cf_config["r2_endpoint"],
                aws_access_key_id=os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
                config=Config(region_name="auto", retries={"max_attempts": 3}),
            )

            # Test connection
            client.head_bucket(Bucket=self.bucket_name)
            logger.info("Connected to Cloudflare R2 bucket: %s", self.bucket_name)
            return client

        except ImportError as e:
            logger.error(
                "boto3 is required for Cloudflare uploads. Install with: uv add boto3"
            )
            raise ImportError("boto3 is required for Cloudflare uploads") from e
        except Exception as e:
            logger.error("Failed to initialize R2 client: %s", e)
            logger.error(
                "Make sure CLOUDFLARE_R2_ACCESS_KEY_ID and "
                "CLOUDFLARE_R2_SECRET_ACCESS_KEY are set"
            )
            raise

    def upload_package(self, upload_package: Dict):
        """
        Upload complete processing package to Cloudflare

        Args:
            upload_package: Package containing videos, metadata, thumbnails, etc.
        """
        if self.r2_client is None:
            logger.warning("Cloudflare R2 client not available, skipping upload")
            return

        logger.info("Starting Cloudflare upload...")

        try:
            # 1. Upload processed videos
            self._upload_videos(
                upload_package["processed_videos"], upload_package["video_info"]
            )

            # 2. Upload thumbnail
            self._upload_thumbnail(
                upload_package["thumbnail"], upload_package["video_info"]
            )

            # 3. Upload metadata to R2
            self._upload_metadata_files(upload_package)

            # 4. Update KV storage with video index
            self._update_kv_storage(upload_package)

            logger.info("Cloudflare upload completed successfully")

        except Exception as e:
            logger.error("Cloudflare upload failed: %s", e)
            raise

    def _upload_videos(self, video_paths: List[str], video_info: Dict):
        """Upload processed video files to R2"""
        video_name = video_info["processed_name"]

        for video_path in video_paths:
            video_file = Path(video_path)

            # Determine S3 key based on video format/resolution
            if "1080p" in video_file.name:
                s3_key = f"videos/processed/{video_name}/{video_name}_1080p.mp4"
            elif "720p" in video_file.name:
                s3_key = f"videos/processed/{video_name}/{video_name}_720p.mp4"
            else:
                s3_key = f"videos/processed/{video_name}/{video_file.name}"

            logger.info("Uploading video: %s -> %s", video_file.name, s3_key)

            try:
                # Upload with appropriate content type and caching headers
                self.r2_client.upload_file(
                    str(video_path),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        "ContentType": "video/mp4",
                        "CacheControl": "public, max-age=86400",  # 24 hours
                        "Metadata": {
                            "original-filename": video_info["filename"],
                            "processing-date": video_info["processing_date"],
                            "duration": str(video_info["duration"]),
                            "resolution": f"{video_info['width']}x{video_info['height']}",
                        },
                    },
                )
                logger.info("Successfully uploaded: %s", s3_key)

            except Exception as e:
                logger.error("Failed to upload %s: %s", video_path, e)
                raise

    def _upload_thumbnail(self, thumbnail_path: str, video_info: Dict):
        """Upload video thumbnail to R2"""
        if self.r2_client is None:
            return

        # thumbnail_file = Path(thumbnail_path)  # Unused variable
        video_name = video_info["processed_name"]
        s3_key = f"videos/thumbnails/{video_name}_thumbnail.jpg"

        logger.info("Uploading thumbnail: %s", s3_key)

        try:
            self.r2_client.upload_file(
                thumbnail_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    "ContentType": "image/jpeg",
                    "CacheControl": "public, max-age=604800",  # 7 days
                    "Metadata": {
                        "video-name": video_name,
                        "original-filename": video_info["filename"],
                    },
                },
            )
            logger.info("Successfully uploaded thumbnail: %s", s3_key)

        except Exception as e:
            logger.error("Failed to upload thumbnail: %s", e)
            raise

    def _upload_metadata_files(self, upload_package: Dict):
        """Upload metadata files to R2"""
        if self.r2_client is None:
            return

        video_name = upload_package["video_info"]["processed_name"]
        metadata = upload_package["metadata"]
        gallery_data = upload_package["gallery_data"]

        # Upload main metadata
        metadata_key = f"metadata/videos/{video_name}/metadata.json"
        self._upload_json_to_r2(metadata, metadata_key)

        # Upload gallery data
        gallery_key = f"metadata/galleries/{video_name}/gallery.json"
        self._upload_json_to_r2(gallery_data, gallery_key)

        # Upload contestant timeline separately (for efficient loading)
        timeline_key = f"metadata/timelines/{video_name}/timeline.json"
        self._upload_json_to_r2(metadata["contestant_timeline"], timeline_key)

        # Upload processing summary
        summary_key = f"metadata/summaries/{video_name}/summary.json"
        self._upload_json_to_r2(metadata["processing_summary"], summary_key)

    def _upload_json_to_r2(self, data: Dict, s3_key: str):
        """Upload JSON data to R2"""
        if self.r2_client is None:
            return

        logger.info("Uploading metadata: %s", s3_key)

        try:
            json_content = json.dumps(data, ensure_ascii=False, indent=2)

            self.r2_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_content.encode("utf-8"),
                ContentType="application/json",
                CacheControl="public, max-age=3600",  # 1 hour
                Metadata={
                    "content-encoding": "utf-8",
                    "upload-timestamp": str(int(time.time())),
                },
            )
            logger.info("Successfully uploaded: %s", s3_key)

        except Exception as e:
            logger.error("Failed to upload JSON to %s: %s", s3_key, e)
            raise

    def _update_kv_storage(self, upload_package: Dict):
        """Update Cloudflare KV storage with video index"""
        if self.r2_client is None:
            return

        video_info = upload_package["video_info"]
        metadata = upload_package["metadata"]

        # Create video index entry
        video_entry = {
            "id": video_info["processed_name"],
            "name": video_info["filename"],
            "duration": video_info["duration"],
            "width": video_info["width"],
            "height": video_info["height"],
            "fps": video_info["fps"],
            "processing_date": video_info["processing_date"],
            "total_recognitions": metadata["processing_summary"]["total_recognitions"],
            "unique_contestants": metadata["processing_summary"]["unique_contestants"],
            "recognition_rate": metadata["processing_summary"]["recognition_rate"],
            "stream_urls": {
                "1080p": (
                    f"https://{self.bucket_name}.{self.account_id}."
                    f"r2.cloudflarestorage.com/videos/processed/"
                    f"{video_info['processed_name']}/"
                    f"{video_info['processed_name']}_1080p.mp4"
                ),
                "720p": (
                    f"https://{self.bucket_name}.{self.account_id}."
                    f"r2.cloudflarestorage.com/videos/processed/"
                    f"{video_info['processed_name']}/"
                    f"{video_info['processed_name']}_720p.mp4"
                ),
            },
            "thumbnail_url": (
                f"https://{self.bucket_name}.{self.account_id}."
                f"r2.cloudflarestorage.com/videos/thumbnails/"
                f"{video_info['processed_name']}_thumbnail.jpg"
            ),
            "metadata_urls": {
                "metadata": (
                    f"https://{self.bucket_name}.{self.account_id}."
                    f"r2.cloudflarestorage.com/metadata/videos/"
                    f"{video_info['processed_name']}/metadata.json"
                ),
                "gallery": (
                    f"https://{self.bucket_name}.{self.account_id}."
                    f"r2.cloudflarestorage.com/metadata/galleries/"
                    f"{video_info['processed_name']}/gallery.json"
                ),
                "timeline": (
                    f"https://{self.bucket_name}.{self.account_id}."
                    f"r2.cloudflarestorage.com/metadata/timelines/"
                    f"{video_info['processed_name']}/timeline.json"
                ),
            },
        }

        # Note: KV API integration would go here
        # For MVP, we'll store this as a JSON file in R2 instead
        video_index_key = f"index/videos/{video_info['processed_name']}.json"
        self._upload_json_to_r2(video_entry, video_index_key)

        logger.info("Updated video index for: %s", video_info["processed_name"])

    def list_uploaded_videos(self) -> List[Dict]:
        """List all uploaded videos from R2"""
        if self.r2_client is None:
            return []

        try:
            response = self.r2_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix="index/videos/", Delimiter="/"
            )

            videos = []
            for obj in response.get("Contents", []):
                if obj["Key"].endswith(".json"):
                    # Get video index
                    video_data = self.r2_client.get_object(
                        Bucket=self.bucket_name, Key=obj["Key"]
                    )
                    video_info = json.loads(video_data["Body"].read().decode("utf-8"))
                    videos.append(video_info)

            return videos

        except Exception as e:
            logger.error("Failed to list uploaded videos: %s", e)
            return []

    def delete_video(self, video_name: str):
        """Delete all files related to a video"""
        prefixes = [
            f"videos/processed/{video_name}/",
            f"videos/thumbnails/{video_name}_",
            f"metadata/videos/{video_name}/",
            f"metadata/galleries/{video_name}/",
            f"metadata/timelines/{video_name}/",
            f"metadata/summaries/{video_name}/",
            f"index/videos/{video_name}.json",
        ]

        logger.info("Deleting video: %s", video_name)

        for prefix in prefixes:
            try:
                # List objects with prefix
                response = self.r2_client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=prefix
                )

                # Delete objects
                objects_to_delete = [
                    {"Key": obj["Key"]} for obj in response.get("Contents", [])
                ]

                if objects_to_delete:
                    self.r2_client.delete_objects(
                        Bucket=self.bucket_name, Delete={"Objects": objects_to_delete}
                    )
                    logger.info(
                        "Deleted %d objects with prefix: %s",
                        len(objects_to_delete),
                        prefix,
                    )

            except Exception as e:
                logger.error("Failed to delete objects with prefix %s: %s", prefix, e)

        logger.info("Video deletion completed: %s", video_name)


class CloudflareEnvironmentSetup:
    """Helper class for setting up Cloudflare environment"""

    @staticmethod
    def print_setup_instructions():
        """Print instructions for setting up Cloudflare credentials"""
        instructions = """
# Cloudflare Setup Instructions

## 1. Create R2 Bucket
- Go to Cloudflare Dashboard > R2 Object Storage
- Create a new bucket named 'mv-face-recognition'
- Note your Account ID

## 2. Generate R2 API Token
- Go to R2 > Manage R2 API tokens
- Create a new token with:
  - Permission: Object Read & Write
  - Bucket: mv-face-recognition
- Save the Access Key ID and Secret Access Key

## 3. Set Environment Variables
export CLOUDFLARE_ACCOUNT_ID="your-account-id"
export CLOUDFLARE_API_TOKEN="your-api-token"
export CLOUDFLARE_R2_ACCESS_KEY_ID="your-r2-access-key"
export CLOUDFLARE_R2_SECRET_ACCESS_KEY="your-r2-secret-key"

## 4. Update Configuration
Edit config/processing_config.yaml:
- Set cloudflare.account_id to your Account ID
- Verify cloudflare.r2_bucket name matches your bucket

## 5. Test Connection
python -c "from cloudflare_uploader import CloudflareUploader; import yaml; config = yaml.safe_load(open('config/processing_config.yaml')); uploader = CloudflareUploader(config)"
"""
        print(instructions)
