#!/usr/bin/env python3
"""
Script to create and upload HF Dataset for MV Face Recognition
Run this to set up the dataset repository with multi-quality videos
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    from datasets import Dataset, DatasetDict
    from huggingface_hub import create_repo, login
    DATASETS_AVAILABLE = True
except ImportError:
    print("❌ Required packages not installed. Install with:")
    print("   pip install datasets huggingface_hub")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HFDatasetCreator:
    """Creates and uploads the MV Face Recognition dataset to HF"""

    def __init__(self,
                 dataset_name: str = "yellowcandle/mv-face-recognition-data",
                 staging_dir: str = "dataset_staging"):
        self.dataset_name = dataset_name
        self.staging_dir = Path(staging_dir)
        self.videos_dir = self.staging_dir / "videos"

    def authenticate(self):
        """Authenticate with Hugging Face"""
        print("🔐 Authenticating with Hugging Face...")
        try:
            # Check if already logged in
            from huggingface_hub import whoami
            user_info = whoami()
            print(f"✅ Already logged in as: {user_info['name']}")
            return True
        except:
            pass

        print("Please log in to Hugging Face:")
        print("1. Get your token from: https://huggingface.co/settings/tokens")
        print("2. Create a token with 'write' permissions")

        token = input("Enter your HF token (or press Enter to use login flow): ").strip()

        if token:
            login(token=token)
        else:
            login()

        print("✅ Authentication successful!")
        return True

    def create_repository(self):
        """Create the dataset repository"""
        print(f"📂 Creating dataset repository: {self.dataset_name}")

        try:
            create_repo(
                repo_id=self.dataset_name,
                repo_type="dataset",
                exist_ok=True,
                private=False
            )
            print("✅ Repository created/verified")
            return True
        except Exception as e:
            print(f"❌ Error creating repository: {e}")
            return False

    def upload_videos_individually(self):
        """Upload videos one by one to avoid memory issues"""
        qualities = ["480p", "720p", "1080p"]

        for quality in qualities:
            print(f"📹 Uploading {quality} videos...")

            quality_dir = self.videos_dir / {
                "480p": "optimized_480p",
                "720p": "optimized_720p",
                "1080p": "original_1080p"
            }[quality]

            if not quality_dir.exists():
                print(f"⚠️ Directory not found: {quality_dir}")
                continue

            # Get video files
            video_files = list(quality_dir.glob("*.mp4"))

            if not video_files:
                print(f"⚠️ No videos found in {quality_dir}")
                continue

            # Upload each video individually
            for i, video_file in enumerate(video_files):
                file_size = video_file.stat().st_size
                size_mb = round(file_size / (1024*1024), 1)

                print(f"  📤 Uploading: {video_file.name} ({size_mb}MB) [{i+1}/{len(video_files)}]")

                # Load only this video into memory
                with open(video_file, 'rb') as f:
                    video_data = f.read()

                # Create single-video dataset
                entry = {
                    'video': video_data,
                    'filename': video_file.name,
                    'quality': quality,
                    'size_bytes': file_size,
                    'size_mb': size_mb
                }

                single_dataset = Dataset.from_list([entry])

                try:
                    # Upload this video
                    single_dataset.push_to_hub(
                        self.dataset_name,
                        config_name=f"videos_{quality}",
                        split=f"video_{i:02d}",
                        private=False
                    )
                    print(f"  ✅ Uploaded: {video_file.name}")

                except Exception as e:
                    print(f"  ❌ Error uploading {video_file.name}: {e}")
                    return False

                # Clear from memory
                del video_data, entry, single_dataset

        return True

    def prepare_metadata_dataset(self):
        """Prepare metadata dataset"""
        print("📄 Preparing metadata dataset...")

        metadata_file = self.videos_dir / "metadata.json"
        if not metadata_file.exists():
            print(f"❌ Metadata file not found: {metadata_file}")
            return None

        with open(metadata_file, encoding='utf-8') as f:
            metadata_content = f.read()

        metadata_dataset = Dataset.from_list([{
            'filename': 'metadata.json',
            'content': metadata_content
        }])

        print("✅ Metadata dataset prepared")
        return metadata_dataset

    def prepare_contestant_data(self):
        """Prepare contestant photos and embeddings"""
        print("👥 Preparing contestant data...")

        # Embeddings package
        embeddings_file = Path("embeddings_package.json")
        if embeddings_file.exists():
            with open(embeddings_file, encoding='utf-8') as f:
                embeddings_content = f.read()

            embeddings_dataset = Dataset.from_list([{
                'filename': 'embeddings_package.json',
                'content': embeddings_content
            }])
            print("✅ Embeddings package prepared")
            return {'embeddings': embeddings_dataset}
        else:
            print("⚠️ Embeddings package not found")
            return {}

    def upload_dataset(self, datasets_dict):
        """Upload all datasets to HF"""
        print(f"🚀 Uploading dataset to: {self.dataset_name}")

        # Create DatasetDict
        full_dataset = DatasetDict(datasets_dict)

        try:
            # Push to hub
            full_dataset.push_to_hub(
                self.dataset_name,
                private=False
            )
            print("✅ Dataset uploaded successfully!")
            return True

        except Exception as e:
            print(f"❌ Error uploading dataset: {e}")
            return False

    def create_dataset_card(self):
        """Create README.md for the dataset"""
        readme_content = f"""
# MV Face Recognition Video Dataset

This dataset contains multi-quality videos for the MV Face Recognition system.

## Dataset Structure

### Video Qualities

- **480p**: Mobile-friendly, fast processing (~30MB per video)
- **720p**: Balanced quality and performance (~40MB per video)
- **1080p**: Best quality, detailed analysis (~200MB per video)

### Contents

- `videos_480p`: 5 videos in 480p resolution (854x480)
- `videos_720p`: 5 videos in 720p resolution (1280x720)
- `videos_1080p`: 5 videos in 1080p resolution (1920x1080)
- `metadata`: Video metadata and quality information
- `embeddings`: Pre-computed face embeddings for 95+ contestants

## Usage

```python
from datasets import load_dataset

# Load 720p videos (recommended)
dataset = load_dataset("{self.dataset_name}", name="videos_720p")

# Load metadata
metadata = load_dataset("{self.dataset_name}", name="metadata")

# Load embeddings
embeddings = load_dataset("{self.dataset_name}", name="embeddings")
```

## Integration

This dataset is designed to work with the [MV Face Recognition](https://huggingface.co/spaces/yellowcandle/mv-face-recognition) Gradio application, providing scalable video storage beyond the 1GB Space limit.

## License

This dataset is provided for research and educational purposes.

## Videos

The dataset contains 5 music videos from 《全民造星IV》(King Maker IV):

1. 主題曲 《前傳》MV 2021夏の首部曲：造星の駅
2. 主題曲 《前傳》MV 2021夏の次部曲：始発の駅
3. 主題曲 《前傳》MV 2021夏の三部曲：女團の駅
4. 極限拍MV
5. 播前熱身！率先表演《前傳》

Total duration: ~22 minutes across all videos.
"""

        readme_path = self.staging_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content.strip())

        print("✅ Dataset README created")
        return readme_path

    def run(self):
        """Run the full dataset creation process"""
        print("🎬 Creating HF Dataset for MV Face Recognition")
        print("=" * 50)

        # Check staging directory
        if not self.staging_dir.exists():
            print(f"❌ Staging directory not found: {self.staging_dir}")
            print("Please run video preparation first")
            return False

        # Step 1: Authenticate
        if not self.authenticate():
            return False

        # Step 2: Create repository
        if not self.create_repository():
            return False

        # Step 3: Upload videos individually (memory efficient)
        print("\n📤 Uploading videos (memory efficient approach)...")
        if not self.upload_videos_individually():
            print("\n❌ Video upload failed")
            return False

        # Step 4: Prepare and upload metadata and embeddings
        print("\n📦 Preparing metadata and embeddings...")

        metadata_dataset = self.prepare_metadata_dataset()
        contestant_datasets = self.prepare_contestant_data()

        # Combine non-video datasets
        other_datasets = {}
        if metadata_dataset:
            other_datasets['metadata'] = metadata_dataset
        other_datasets.update(contestant_datasets)

        if other_datasets:
            print("\n📊 Non-video dataset summary:")
            for name, dataset in other_datasets.items():
                print(f"  - {name}: {len(dataset)} items")

            print("\n🚀 Uploading metadata and embeddings...")
            if not self.upload_dataset(other_datasets):
                print("\n❌ Metadata/embeddings upload failed")
                return False

        # Step 5: Create README
        self.create_dataset_card()

        print("\n🎉 Dataset creation completed successfully!")
        print(f"📍 Dataset URL: https://huggingface.co/datasets/{self.dataset_name}")
        return True

def main():
    """Main function"""
    if len(sys.argv) > 1:
        dataset_name = sys.argv[1]
    else:
        dataset_name = "yellowcandle/mv-face-recognition-data"

    creator = HFDatasetCreator(dataset_name=dataset_name)

    success = creator.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
