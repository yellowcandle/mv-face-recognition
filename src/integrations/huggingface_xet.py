"""
HuggingFace XET Integration for MV Face Recognition.

This module provides integration with HuggingFace's XET storage for:
- Contestant CSV data
- Face embeddings (.npy files)
- Processed videos
- Flagged face images for training

Usage:
    from src.integrations.huggingface_xet import HuggingFaceDataset

    # Initialize dataset
    dataset = HuggingFaceDataset(
        repo_id="yellowcandle/mv-face-recognition-data",
        token=os.getenv("HF_TOKEN")
    )

    # Sync contestant data
    dataset.upload_contestant_data()

    # Upload embeddings
    dataset.upload_embeddings()

    # Download for Modal processing
    dataset.download_to_modal_volume()
"""

import os
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download, upload_file, upload_folder
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False


class HuggingFaceDataset:
    """
    Manages the contestant dataset on HuggingFace XET storage.

    Dataset structure on HuggingFace:
        mv-face-recognition-data/
        ├── metadata/
        │   ├── contestant_info.csv
        │   ├── flagged_faces.json
        │   └── embedding_manifest.json
        ├── embeddings/
        │   ├── contestant_1/
        │   │   ├── base_embedding.npy
        │   │   └── flagged_001.npy
        │   ├── contestant_2/
        │   │   └── ...
        │   └── ...
        ├── photos/
        │   ├── contestant_1/
        │   │   ├── photo_001.jpg
        │   │   └── flagged_001.jpg
        │   └── ...
        └── videos/
            ├── processed/
            │   ├── video_1_annotated.mp4
            │   └── ...
            └── metadata/
                ├── video_1_metadata.json
                └── ...
    """

    def __init__(
        self,
        repo_id: str = "yellowcandle/mv-face-recognition-data",
        token: Optional[str] = None,
        local_cache_dir: Optional[str] = None,
    ):
        """
        Initialize HuggingFace dataset connection.

        Args:
            repo_id: HuggingFace repository ID (user/repo-name)
            token: HuggingFace API token (optional, uses HF_TOKEN env var)
            local_cache_dir: Local directory for caching downloads
        """
        if not HF_AVAILABLE:
            raise ImportError(
                "huggingface_hub is required. Install with: pip install huggingface_hub"
            )

        self.repo_id = repo_id
        self.token = token or os.getenv("HF_TOKEN")
        self.local_cache_dir = local_cache_dir or os.path.join(
            tempfile.gettempdir(), "hf_mv_cache"
        )
        self.api = HfApi(token=self.token)

        # Ensure cache directory exists
        os.makedirs(self.local_cache_dir, exist_ok=True)

    def ensure_repo_exists(self, repo_type: str = "dataset") -> bool:
        """
        Ensure the HuggingFace repository exists, create if not.

        Args:
            repo_type: Type of repository ("dataset", "model", or "space")

        Returns:
            True if repo exists or was created successfully
        """
        try:
            self.api.repo_info(repo_id=self.repo_id, repo_type=repo_type)
            return True
        except Exception:
            try:
                self.api.create_repo(
                    repo_id=self.repo_id,
                    repo_type=repo_type,
                    private=False,
                    exist_ok=True,
                )
                print(f"✅ Created HuggingFace repository: {self.repo_id}")
                return True
            except Exception as e:
                print(f"❌ Failed to create repository: {e}")
                return False

    def upload_contestant_data(
        self,
        csv_path: str = "metadata/contestant_info.csv",
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Upload contestant CSV data to HuggingFace.

        Args:
            csv_path: Path to the contestant CSV file
            additional_metadata: Optional additional metadata to include

        Returns:
            True if upload successful
        """
        if not os.path.exists(csv_path):
            print(f"❌ Contestant CSV not found: {csv_path}")
            return False

        try:
            # Upload the CSV file
            upload_file(
                path_or_fileobj=csv_path,
                path_in_repo="metadata/contestant_info.csv",
                repo_id=self.repo_id,
                repo_type="dataset",
                token=self.token,
                commit_message=f"Update contestant data - {datetime.now().isoformat()}",
            )

            # Upload additional metadata if provided
            if additional_metadata:
                metadata_path = os.path.join(self.local_cache_dir, "metadata.json")
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(additional_metadata, f, indent=2, ensure_ascii=False)

                upload_file(
                    path_or_fileobj=metadata_path,
                    path_in_repo="metadata/additional_metadata.json",
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    token=self.token,
                )

            print(f"✅ Uploaded contestant data to {self.repo_id}")
            return True

        except Exception as e:
            print(f"❌ Failed to upload contestant data: {e}")
            return False

    def upload_embeddings(
        self,
        embeddings_dir: str = "source/photo/contestants",
        batch_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Upload face embeddings to HuggingFace.

        Args:
            embeddings_dir: Directory containing contestant embedding files
            batch_size: Number of embeddings to upload per batch

        Returns:
            Dictionary with upload statistics
        """
        if not NP_AVAILABLE:
            raise ImportError("numpy is required for embedding upload")

        stats = {
            "uploaded": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        embeddings_path = Path(embeddings_dir)
        if not embeddings_path.exists():
            print(f"❌ Embeddings directory not found: {embeddings_dir}")
            return stats

        # Find all embedding files
        embedding_files = list(embeddings_path.rglob("*_embedding.npy"))

        print(f"📦 Found {len(embedding_files)} embedding files to upload")

        for embedding_file in embedding_files:
            try:
                # Extract contestant info from path
                contestant_dir = embedding_file.parent.name
                filename = embedding_file.name

                # Upload to HuggingFace
                remote_path = f"embeddings/{contestant_dir}/{filename}"

                upload_file(
                    path_or_fileobj=str(embedding_file),
                    path_in_repo=remote_path,
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    token=self.token,
                    commit_message=f"Upload embedding: {contestant_dir}/{filename}",
                )

                stats["uploaded"] += 1
                print(f"  ✅ Uploaded: {remote_path}")

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"file": str(embedding_file), "error": str(e)})
                print(f"  ❌ Failed: {embedding_file} - {e}")

        print(f"\n📊 Upload Summary: {stats['uploaded']} uploaded, {stats['failed']} failed")
        return stats

    def upload_flagged_face(
        self,
        image_data: bytes,
        embedding: Any,
        contestant_id: int,
        video_id: str,
        timestamp: float,
        bbox: List[int],
        confidence: float,
        user_label: str,
    ) -> Dict[str, Any]:
        """
        Upload a user-flagged face to improve recognition accuracy.

        Args:
            image_data: Face image data (cropped face region)
            embedding: Face embedding vector (512-dim numpy array)
            contestant_id: ID of the contestant this face belongs to
            video_id: ID of the source video
            timestamp: Timestamp in the video where face was detected
            bbox: Bounding box coordinates [x, y, width, height]
            confidence: Original detection confidence
            user_label: User-provided label/confirmation

        Returns:
            Dictionary with upload result
        """
        if not NP_AVAILABLE:
            raise ImportError("numpy is required for flagged face upload")

        result = {
            "success": False,
            "face_id": None,
            "error": None,
        }

        try:
            # Generate unique face ID
            face_id = f"flag_{contestant_id}_{video_id}_{int(timestamp * 1000)}"
            result["face_id"] = face_id

            # Create temporary files
            temp_dir = os.path.join(self.local_cache_dir, "flagged", face_id)
            os.makedirs(temp_dir, exist_ok=True)

            # Save image
            image_path = os.path.join(temp_dir, "face.jpg")
            with open(image_path, "wb") as f:
                f.write(image_data)

            # Save embedding
            embedding_path = os.path.join(temp_dir, "embedding.npy")
            if isinstance(embedding, list):
                embedding = np.array(embedding)
            np.save(embedding_path, embedding)

            # Save metadata
            metadata = {
                "face_id": face_id,
                "contestant_id": contestant_id,
                "video_id": video_id,
                "timestamp": timestamp,
                "bbox": bbox,
                "original_confidence": confidence,
                "user_label": user_label,
                "flagged_at": datetime.now().isoformat(),
            }
            metadata_path = os.path.join(temp_dir, "metadata.json")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # Upload all files
            for filename in ["face.jpg", "embedding.npy", "metadata.json"]:
                local_path = os.path.join(temp_dir, filename)
                remote_path = f"flagged_faces/{contestant_id}/{face_id}/{filename}"

                upload_file(
                    path_or_fileobj=local_path,
                    path_in_repo=remote_path,
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    token=self.token,
                    commit_message=f"Add flagged face: {face_id}",
                )

            result["success"] = True
            print(f"✅ Uploaded flagged face: {face_id}")

            # Clean up temp files
            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Failed to upload flagged face: {e}")

        return result

    def download_dataset(
        self,
        target_dir: str,
        include_videos: bool = False,
        include_flagged: bool = True,
    ) -> Dict[str, Any]:
        """
        Download the dataset from HuggingFace to local directory.

        Args:
            target_dir: Local directory to download to
            include_videos: Whether to include processed videos (large files)
            include_flagged: Whether to include flagged face data

        Returns:
            Dictionary with download statistics
        """
        stats = {
            "downloaded_files": 0,
            "total_size_mb": 0,
            "errors": [],
        }

        try:
            # Prepare patterns for selective download
            allow_patterns = [
                "metadata/*",
                "embeddings/**/*",
                "photos/**/*",
            ]

            if include_flagged:
                allow_patterns.append("flagged_faces/**/*")

            if include_videos:
                allow_patterns.append("videos/**/*")

            # Download snapshot
            local_dir = snapshot_download(
                repo_id=self.repo_id,
                repo_type="dataset",
                local_dir=target_dir,
                allow_patterns=allow_patterns,
                token=self.token,
            )

            # Count downloaded files
            for root, dirs, files in os.walk(local_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    stats["downloaded_files"] += 1
                    stats["total_size_mb"] += os.path.getsize(file_path) / (1024 * 1024)

            print(f"✅ Downloaded {stats['downloaded_files']} files ({stats['total_size_mb']:.2f} MB)")

        except Exception as e:
            stats["errors"].append(str(e))
            print(f"❌ Download failed: {e}")

        return stats

    def download_to_modal_volume(
        self,
        volume_path: str = "/data",
    ) -> Dict[str, Any]:
        """
        Download dataset to Modal volume for cloud processing.

        Args:
            volume_path: Path to Modal volume mount point

        Returns:
            Dictionary with download result
        """
        result = {
            "success": False,
            "files_downloaded": 0,
            "paths": {},
        }

        try:
            # Create directories
            os.makedirs(f"{volume_path}/source/photo/contestants", exist_ok=True)
            os.makedirs(f"{volume_path}/metadata", exist_ok=True)
            os.makedirs(f"{volume_path}/data/chroma_db", exist_ok=True)

            # Download metadata
            csv_path = hf_hub_download(
                repo_id=self.repo_id,
                repo_type="dataset",
                filename="metadata/contestant_info.csv",
                local_dir=volume_path,
                token=self.token,
            )
            result["paths"]["contestant_csv"] = csv_path
            result["files_downloaded"] += 1

            # Download embeddings
            embeddings_dir = snapshot_download(
                repo_id=self.repo_id,
                repo_type="dataset",
                local_dir=f"{volume_path}/source/photo",
                allow_patterns=["embeddings/**/*"],
                token=self.token,
            )

            # Move embeddings to correct location
            src_embeddings = os.path.join(embeddings_dir, "embeddings")
            if os.path.exists(src_embeddings):
                for contestant_dir in os.listdir(src_embeddings):
                    src = os.path.join(src_embeddings, contestant_dir)
                    dst = os.path.join(volume_path, "source/photo/contestants", contestant_dir)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                        result["files_downloaded"] += len(os.listdir(src))

            result["paths"]["embeddings_dir"] = f"{volume_path}/source/photo/contestants"
            result["success"] = True

            print(f"✅ Downloaded dataset to Modal volume: {result['files_downloaded']} files")

        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Failed to download to Modal volume: {e}")

        return result

    def get_flagged_faces(
        self,
        contestant_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get list of flagged faces, optionally filtered by contestant.

        Args:
            contestant_id: Optional contestant ID to filter by

        Returns:
            List of flagged face metadata dictionaries
        """
        flagged_faces = []

        try:
            # List files in flagged_faces directory
            files = self.api.list_repo_files(
                repo_id=self.repo_id,
                repo_type="dataset",
            )

            # Filter for metadata files
            metadata_files = [
                f for f in files
                if f.startswith("flagged_faces/") and f.endswith("metadata.json")
            ]

            for metadata_file in metadata_files:
                # Check contestant filter
                if contestant_id is not None:
                    if f"flagged_faces/{contestant_id}/" not in metadata_file:
                        continue

                # Download and parse metadata
                local_path = hf_hub_download(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    filename=metadata_file,
                    token=self.token,
                )

                with open(local_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    flagged_faces.append(metadata)

        except Exception as e:
            print(f"❌ Failed to get flagged faces: {e}")

        return flagged_faces

    def update_embeddings_with_flagged(
        self,
        contestant_id: int,
        output_dir: str,
        averaging_weight: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Update contestant embeddings by incorporating flagged face embeddings.

        This improves recognition accuracy by averaging the base embedding
        with user-confirmed face embeddings.

        Args:
            contestant_id: Contestant ID to update
            output_dir: Directory to save updated embedding
            averaging_weight: Weight for flagged embeddings (0-1)

        Returns:
            Dictionary with update result
        """
        if not NP_AVAILABLE:
            raise ImportError("numpy is required for embedding update")

        result = {
            "success": False,
            "original_embedding": None,
            "flagged_count": 0,
            "new_embedding_path": None,
        }

        try:
            # Get flagged faces for this contestant
            flagged_faces = self.get_flagged_faces(contestant_id=contestant_id)
            result["flagged_count"] = len(flagged_faces)

            if len(flagged_faces) == 0:
                result["error"] = "No flagged faces found"
                return result

            # Download base embedding
            base_embedding = None
            try:
                base_path = hf_hub_download(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    filename=f"embeddings/{contestant_id}/base_embedding.npy",
                    token=self.token,
                )
                base_embedding = np.load(base_path)
                result["original_embedding"] = base_path
            except Exception:
                print(f"⚠️ No base embedding found for contestant {contestant_id}")

            # Collect flagged embeddings
            flagged_embeddings = []
            for face in flagged_faces:
                face_id = face["face_id"]
                try:
                    emb_path = hf_hub_download(
                        repo_id=self.repo_id,
                        repo_type="dataset",
                        filename=f"flagged_faces/{contestant_id}/{face_id}/embedding.npy",
                        token=self.token,
                    )
                    emb = np.load(emb_path)
                    flagged_embeddings.append(emb)
                except Exception as e:
                    print(f"⚠️ Failed to load embedding for {face_id}: {e}")

            if len(flagged_embeddings) == 0:
                result["error"] = "Could not load any flagged embeddings"
                return result

            # Compute average of flagged embeddings
            flagged_avg = np.mean(flagged_embeddings, axis=0)

            # Combine with base embedding if available
            if base_embedding is not None:
                # Weighted average
                updated_embedding = (
                    (1 - averaging_weight) * base_embedding +
                    averaging_weight * flagged_avg
                )
            else:
                # Use flagged average as new base
                updated_embedding = flagged_avg

            # Normalize embedding
            updated_embedding = updated_embedding / np.linalg.norm(updated_embedding)

            # Save updated embedding
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{contestant_id}_embedding.npy")
            np.save(output_path, updated_embedding)
            result["new_embedding_path"] = output_path

            # Upload updated embedding
            upload_file(
                path_or_fileobj=output_path,
                path_in_repo=f"embeddings/{contestant_id}/base_embedding.npy",
                repo_id=self.repo_id,
                repo_type="dataset",
                token=self.token,
                commit_message=f"Update embedding with {len(flagged_embeddings)} flagged faces",
            )

            result["success"] = True
            print(f"✅ Updated embedding for contestant {contestant_id} with {len(flagged_embeddings)} flagged faces")

        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Failed to update embeddings: {e}")

        return result

    def upload_processed_video(
        self,
        video_path: str,
        metadata_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a processed (annotated) video to HuggingFace.

        Args:
            video_path: Path to the annotated video file
            metadata_path: Optional path to video metadata JSON

        Returns:
            Dictionary with upload result
        """
        result = {
            "success": False,
            "video_url": None,
            "error": None,
        }

        try:
            video_filename = os.path.basename(video_path)
            remote_path = f"videos/processed/{video_filename}"

            # Upload video
            upload_file(
                path_or_fileobj=video_path,
                path_in_repo=remote_path,
                repo_id=self.repo_id,
                repo_type="dataset",
                token=self.token,
                commit_message=f"Upload processed video: {video_filename}",
            )

            result["video_url"] = f"https://huggingface.co/datasets/{self.repo_id}/resolve/main/{remote_path}"

            # Upload metadata if provided
            if metadata_path and os.path.exists(metadata_path):
                metadata_filename = os.path.basename(metadata_path)
                upload_file(
                    path_or_fileobj=metadata_path,
                    path_in_repo=f"videos/metadata/{metadata_filename}",
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    token=self.token,
                )

            result["success"] = True
            print(f"✅ Uploaded processed video: {video_filename}")

        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Failed to upload video: {e}")

        return result


def create_dataset_readme(repo_id: str) -> str:
    """Generate README content for the HuggingFace dataset."""
    return f"""---
license: mit
tags:
  - face-recognition
  - video-analysis
  - contestant-identification
language:
  - zh
---

# MV Face Recognition Dataset

This dataset contains face embeddings and metadata for the MV Face Recognition system.

## Dataset Structure

```
{repo_id}/
├── metadata/
│   ├── contestant_info.csv      # Contestant information (ID, name, nickname, age)
│   └── embedding_manifest.json  # Manifest of all embeddings
├── embeddings/
│   └── contestant_{{id}}/
│       └── base_embedding.npy   # 512-dim face embedding
├── flagged_faces/
│   └── contestant_{{id}}/
│       └── flag_{{id}}/
│           ├── face.jpg         # Cropped face image
│           ├── embedding.npy    # Face embedding
│           └── metadata.json    # Detection metadata
└── videos/
    ├── processed/               # Annotated videos
    └── metadata/                # Video processing metadata
```

## Usage

```python
from src.integrations.huggingface_xet import HuggingFaceDataset

# Initialize
dataset = HuggingFaceDataset(repo_id="{repo_id}")

# Download for local processing
dataset.download_dataset("./data")

# Download for Modal cloud processing
dataset.download_to_modal_volume("/data")
```

## License

MIT License - See repository for full license.
"""
