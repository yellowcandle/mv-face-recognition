#!/usr/bin/env python3
"""
Modal processor with HuggingFace XET integration for MV Face Recognition.

This script extends the batch processor to:
1. Download contestant data and embeddings from HuggingFace
2. Process videos using cloud GPUs
3. Update embeddings with user-flagged faces
4. Upload processed videos back to HuggingFace

**Setup:**

1. Install dependencies:
   ```bash
   pip install modal huggingface_hub
   ```

2. Configure Modal:
   ```bash
   modal setup
   ```

3. Set HuggingFace token:
   ```bash
   export HF_TOKEN=your_huggingface_token
   modal secret create hf-secret HF_TOKEN=$HF_TOKEN
   ```

**Usage:**

1. Sync data from HuggingFace and process videos:
   ```bash
   modal run modal_hf_processor.py --sync-from-hf
   ```

2. Update embeddings from flagged faces:
   ```bash
   modal run modal_hf_processor.py --update-embeddings
   ```

3. Upload processed videos to HuggingFace:
   ```bash
   modal run modal_hf_processor.py --upload-results
   ```

4. Full pipeline (sync -> process -> update -> upload):
   ```bash
   modal run modal_hf_processor.py --full-pipeline
   ```
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

from modal import App, Image, Volume, Secret, method

# --- Modal Configuration ---

app = App("mv-face-recognition-hf")

# Docker image with HuggingFace Hub
modal_image = (
    Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "sqlite3", "git-lfs")
    .pip_install_from_requirements("requirements.txt")
    .pip_install(
        "pysqlite3-binary",
        "onnxruntime-gpu",
        "huggingface_hub>=0.32.0",  # XET support
    )
    .add_local_dir("src", "/src")
)

# Persistent volume for data
volume = Volume.from_name("mv-face-recognition-data", create_if_missing=True)
VOL_MOUNT_PATH = Path("/data")

# HuggingFace configuration
HF_REPO_ID = "yellowcandle/mv-face-recognition-data"

# --- Embedding Validation & Regeneration Functions ---

def validate_and_regenerate_embeddings(
    volume_path: Path = VOL_MOUNT_PATH,
    embeddings_subdir: str = "source/photo/contestants",
    photos_subdir: str = "source/photo/contestants/photos",
    metadata_subdir: str = "metadata",
    expected_dim: int = 512,
    upload_to_hf: bool = True,
) -> Dict[str, Any]:
    """
    Validate embeddings at container startup and regenerate if needed.

    This function is called at Modal container startup to ensure embeddings
    are compatible with the current face_recognition library (512-dim).

    Args:
        volume_path: Mount path for persistent volume
        embeddings_subdir: Subdirectory containing embeddings
        photos_subdir: Subdirectory containing contestant photos
        metadata_subdir: Subdirectory containing contestant CSV
        expected_dim: Expected embedding dimension (512 for current library)
        upload_to_hf: Whether to upload regenerated embeddings to HuggingFace

    Returns:
        Dictionary with validation/regeneration results
    """
    from src.face_detector import regenerate_embeddings_from_contestant_photos

    photo_base_dir = volume_path / photos_subdir
    embeddings_dir = volume_path / embeddings_subdir
    metadata_dir = volume_path / metadata_subdir
    contestants_csv = metadata_dir / "contestant_info.csv"

    result = {
        "validated": False,
        "needs_regeneration": False,
        "regenerated": 0,
        "uploaded": 0,
        "dimension": expected_dim,
        "reason": "",
        "errors": [],
    }

    print(f"\n🔍 Validating embeddings...")
    print(f"   Photo dir: {photo_base_dir}")
    print(f"   Embeddings dir: {embeddings_dir}")
    print(f"   Expected dimension: {expected_dim}")

    # Check if embeddings exist
    embedding_files = list(embeddings_dir.glob("*_embedding.npy"))
    print(f"   Found {len(embedding_files)} existing embeddings")

    if not embedding_files:
        result["needs_regeneration"] = True
        result["reason"] = "no_embeddings_found"
        print(f"   ⚠️  No embeddings found")

    # Validate dimensions of existing embeddings
    dimension_mismatches = 0
    for emb_path in embedding_files:
        try:
            import numpy as np
            embedding = np.load(str(emb_path))
            actual_dim = embedding.shape[0] if embedding.ndim == 1 else embedding.shape[1]
            if actual_dim != expected_dim:
                dimension_mismatches += 1
                print(f"   ⚠️  {emb_path.name}: dim={actual_dim}, expected={expected_dim}")
        except Exception as e:
            print(f"   ⚠️  Failed to load {emb_path.name}: {e}")

    if dimension_mismatches > 0:
        result["needs_regeneration"] = True
        result["reason"] = f"dimension_mismatch ({dimension_mismatches} files)"
        print(f"   ⚠️  {dimension_mismatches} embeddings have wrong dimension")

    # Check if CSV exists for regeneration
    if result["needs_regeneration"] and not contestants_csv.exists():
        result["errors"].append(f"Contestant CSV not found: {contestants_csv}")
        print(f"   ❌ Cannot regenerate: CSV not found")
        return result

    # Regenerate if needed
    if result["needs_regeneration"]:
        print(f"\n🔄 Regenerating embeddings...")
        start_time = time.time()

        regen_result = regenerate_embeddings_from_contestant_photos(
            photo_base_dir=photo_base_dir,
            embeddings_output_dir=embeddings_dir,
            contestants_csv_path=contestants_csv,
            expected_dim=expected_dim,
        )

        result["regenerated"] = regen_result.regenerated_count
        result["duration"] = regen_result.duration_seconds

        if regen_result.success:
            print(f"   ✅ Regenerated {regen_result.regenerated_count} embeddings in {regen_result.duration_seconds:.1f}s")

            # Upload to HuggingFace if requested
            if upload_to_hf:
                print(f"\n📤 Uploading regenerated embeddings to HuggingFace...")
                try:
                    from huggingface_hub import HfApi
                    token = os.environ.get("HF_TOKEN")
                    if token:
                        api = HfApi(token=token)

                        # Upload each embedding
                        for emb_path in embeddings_dir.glob("*_embedding.npy"):
                            try:
                                api.upload_file(
                                    path_or_fileobj=str(emb_path),
                                    path_in_repo=f"embeddings/{emb_path.name}",
                                    repo_id=HF_REPO_ID,
                                    repo_type="dataset",
                                    token=token,
                                )
                                result["uploaded"] += 1
                            except Exception as e:
                                result["errors"].append(f"Upload failed: {emb_path.name}: {e}")

                        print(f"   ✅ Uploaded {result['uploaded']} embeddings to HuggingFace")
                    else:
                        print(f"   ⚠️  No HF_TOKEN, skipping upload")
                except Exception as e:
                    result["errors"].append(f"HuggingFace upload failed: {e}")
                    print(f"   ⚠️  Upload failed: {e}")

            # Commit volume changes
            try:
                volume.commit()
                print(f"   💾 Volume committed")
            except Exception as e:
                result["errors"].append(f"Volume commit failed: {e}")
                print(f"   ⚠️  Volume commit failed: {e}")
        else:
            print(f"   ❌ Regeneration failed: {regen_result.failed_contestants}")
            result["errors"] = [str(f) for f in regen_result.failed_contestants]

    # Commit volume even if no regeneration (to persist any changes)
    if not result["needs_regeneration"]:
        try:
            volume.commit()
        except Exception as e:
            print(f"   ⚠️  Volume commit failed: {e}")

    result["validated"] = True
    print(f"\n✅ Embedding validation complete")
    print(f"   Valid: {not result['needs_regeneration']}")
    print(f"   Regenerated: {result['regenerated']}")
    print(f"   Uploaded: {result['uploaded']}")

    return result


# --- HuggingFace Sync Function ---

@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    secrets=[Secret.from_name("hf-secret")],
    timeout=3600,
)
def sync_from_huggingface(
    include_videos: bool = False,
    include_flagged: bool = True,
) -> Dict[str, Any]:
    """
    Download contestant data and embeddings from HuggingFace XET.
    """
    from huggingface_hub import snapshot_download, hf_hub_download
    import shutil

    result = {
        "success": False,
        "files_downloaded": 0,
        "paths": {},
        "errors": [],
    }

    try:
        token = os.environ.get("HF_TOKEN")
        print(f"🔄 Syncing from HuggingFace: {HF_REPO_ID}")

        # Create directories
        os.makedirs(VOL_MOUNT_PATH / "source/photo/contestants", exist_ok=True)
        os.makedirs(VOL_MOUNT_PATH / "metadata", exist_ok=True)
        os.makedirs(VOL_MOUNT_PATH / "data/chroma_db", exist_ok=True)

        # Download patterns
        allow_patterns = [
            "metadata/*",
            "embeddings/**/*",
        ]
        if include_flagged:
            allow_patterns.append("flagged_faces/**/*")
        if include_videos:
            allow_patterns.append("videos/**/*")

        # Download snapshot
        local_dir = snapshot_download(
            repo_id=HF_REPO_ID,
            repo_type="dataset",
            local_dir=str(VOL_MOUNT_PATH / "hf_cache"),
            allow_patterns=allow_patterns,
            token=token,
        )

        print(f"✅ Downloaded to: {local_dir}")

        # Copy metadata
        metadata_src = Path(local_dir) / "metadata"
        if metadata_src.exists():
            for file in metadata_src.glob("*"):
                dst = VOL_MOUNT_PATH / "metadata" / file.name
                shutil.copy2(file, dst)
                result["files_downloaded"] += 1
                print(f"  📄 {file.name}")

        # Copy embeddings to correct structure
        embeddings_src = Path(local_dir) / "embeddings"
        if embeddings_src.exists():
            for contestant_dir in embeddings_src.iterdir():
                if contestant_dir.is_dir():
                    dst_dir = VOL_MOUNT_PATH / "source/photo/contestants" / contestant_dir.name
                    os.makedirs(dst_dir, exist_ok=True)
                    for file in contestant_dir.glob("*"):
                        shutil.copy2(file, dst_dir / file.name)
                        result["files_downloaded"] += 1
            print(f"  📦 Copied embeddings: {result['files_downloaded']} files")

        # Copy flagged faces if requested
        if include_flagged:
            flagged_src = Path(local_dir) / "flagged_faces"
            if flagged_src.exists():
                dst_flagged = VOL_MOUNT_PATH / "flagged_faces"
                shutil.copytree(flagged_src, dst_flagged, dirs_exist_ok=True)
                flagged_count = sum(1 for _ in flagged_src.rglob("*") if _.is_file())
                result["files_downloaded"] += flagged_count
                print(f"  🏷️ Copied {flagged_count} flagged face files")

        # Copy source videos if requested
        if include_videos:
            videos_src = Path(local_dir) / "videos" / "source"
            if videos_src.exists():
                dst_videos = VOL_MOUNT_PATH / "source/videos"
                os.makedirs(dst_videos, exist_ok=True)
                video_count = 0
                for video_file in videos_src.glob("*"):
                    if video_file.is_file() and video_file.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']:
                        shutil.copy2(video_file, dst_videos / video_file.name)
                        video_count += 1
                        result["files_downloaded"] += 1
                        file_size_mb = video_file.stat().st_size / (1024 * 1024)
                        print(f"  📹 {video_file.name} ({file_size_mb:.2f} MB)")
                if video_count > 0:
                    print(f"  ✅ Copied {video_count} source video(s)")

        result["success"] = True
        result["paths"] = {
            "metadata": str(VOL_MOUNT_PATH / "metadata"),
            "embeddings": str(VOL_MOUNT_PATH / "source/photo/contestants"),
            "flagged": str(VOL_MOUNT_PATH / "flagged_faces"),
            "videos": str(VOL_MOUNT_PATH / "source/videos"),
        }

        # Commit volume changes
        volume.commit()

        print(f"✅ Sync complete: {result['files_downloaded']} files")

    except Exception as e:
        result["errors"].append(str(e))
        print(f"❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()

    return result


# --- Embedding Update Function ---

@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    secrets=[Secret.from_name("hf-secret")],
    gpu="T4",
    timeout=7200,
)
def update_embeddings_from_flagged(
    contestant_id: Optional[int] = None,
    averaging_weight: float = 0.3,
) -> Dict[str, Any]:
    """
    Update contestant embeddings using user-flagged faces.

    This improves recognition accuracy by incorporating confirmed face samples.
    """
    import numpy as np
    from huggingface_hub import upload_file

    # Fix SQLite for ChromaDB
    try:
        import pysqlite3
        sys.modules["sqlite3"] = pysqlite3
    except ImportError:
        pass

    sys.path.insert(0, "/src")

    result = {
        "success": False,
        "contestants_updated": [],
        "errors": [],
    }

    try:
        token = os.environ.get("HF_TOKEN")
        flagged_dir = VOL_MOUNT_PATH / "flagged_faces"

        if not flagged_dir.exists():
            result["errors"].append("No flagged faces directory found")
            return result

        # Get list of contestants to update
        if contestant_id:
            contestants_to_update = [contestant_id]
        else:
            # Update all contestants with flagged faces
            contestants_to_update = [
                int(d.name) for d in flagged_dir.iterdir()
                if d.is_dir() and d.name.isdigit()
            ]

        print(f"📊 Updating embeddings for {len(contestants_to_update)} contestants")

        for cid in contestants_to_update:
            contestant_flagged = flagged_dir / str(cid)
            if not contestant_flagged.exists():
                continue

            print(f"\n🔧 Processing contestant {cid}")

            # Load existing embedding
            contestant_dir = VOL_MOUNT_PATH / "source/photo/contestants" / str(cid)
            base_embedding = None
            base_path = contestant_dir / "base_embedding.npy"

            if base_path.exists():
                base_embedding = np.load(base_path)
                print(f"  📥 Loaded base embedding: {base_embedding.shape}")

            # Load flagged embeddings
            flagged_embeddings = []
            for flag_dir in contestant_flagged.iterdir():
                if flag_dir.is_dir():
                    emb_file = flag_dir / "embedding.npy"
                    if emb_file.exists():
                        emb = np.load(emb_file)
                        flagged_embeddings.append(emb)

            if len(flagged_embeddings) == 0:
                print(f"  ⚠️ No flagged embeddings found")
                continue

            print(f"  📦 Found {len(flagged_embeddings)} flagged embeddings")

            # Compute average of flagged embeddings
            flagged_avg = np.mean(flagged_embeddings, axis=0)

            # Combine with base embedding
            if base_embedding is not None:
                updated_embedding = (
                    (1 - averaging_weight) * base_embedding +
                    averaging_weight * flagged_avg
                )
            else:
                updated_embedding = flagged_avg

            # Normalize
            updated_embedding = updated_embedding / np.linalg.norm(updated_embedding)

            # Save updated embedding
            os.makedirs(contestant_dir, exist_ok=True)
            output_path = contestant_dir / "base_embedding.npy"
            np.save(output_path, updated_embedding)
            print(f"  💾 Saved updated embedding")

            # Upload to HuggingFace
            try:
                upload_file(
                    path_or_fileobj=str(output_path),
                    path_in_repo=f"embeddings/{cid}/base_embedding.npy",
                    repo_id=HF_REPO_ID,
                    repo_type="dataset",
                    token=token,
                    commit_message=f"Update embedding for contestant {cid} with {len(flagged_embeddings)} flagged faces",
                )
                print(f"  ☁️ Uploaded to HuggingFace")
            except Exception as e:
                print(f"  ⚠️ HuggingFace upload failed: {e}")

            result["contestants_updated"].append({
                "contestant_id": cid,
                "flagged_count": len(flagged_embeddings),
                "weight": averaging_weight,
            })

        # Rebuild ChromaDB with updated embeddings
        print("\n🔄 Rebuilding ChromaDB index...")
        try:
            from src.database.chroma_setup import ChromaDBManager

            db_manager = ChromaDBManager(
                persist_directory=str(VOL_MOUNT_PATH / "data/chroma_db")
            )
            db_manager.rebuild_collection()
            print("✅ ChromaDB rebuilt successfully")
        except Exception as e:
            print(f"⚠️ ChromaDB rebuild failed: {e}")
            result["errors"].append(f"ChromaDB rebuild failed: {e}")

        # Commit volume changes
        volume.commit()

        result["success"] = True
        print(f"\n✅ Updated {len(result['contestants_updated'])} contestants")

    except Exception as e:
        result["errors"].append(str(e))
        print(f"❌ Update failed: {e}")
        import traceback
        traceback.print_exc()

    return result


# --- Video Processing Function ---

@app.cls(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    secrets=[Secret.from_name("hf-secret")],
    gpu="T4",
    timeout=7200,
    scaledown_window=300,
)
class VideoProcessor:
    """Process videos with face recognition on Modal GPUs."""

    def __enter__(self):
        """Initialize processor on container start."""
        import pysqlite3
        sys.modules["sqlite3"] = pysqlite3

        sys.path.insert(0, "/src")

        from src.services.enhanced_video_processor import EnhancedVideoProcessor

        print("🚀 Initializing VideoProcessor...")

        # Load config
        config_path = str(VOL_MOUNT_PATH / "config.json")
        if not os.path.exists(config_path):
            # Create default config
            config = {
                "face_detection": {"model_name": "buffalo_l", "detection_threshold": 0.5},
                "face_matching": {"similarity_threshold": 0.25, "max_results": 5},
                "video_processing": {"frame_skip": 5, "output_fps": 24},
                "paths": {
                    "videos_dir": str(VOL_MOUNT_PATH / "source/videos"),
                    "contestants_dir": str(VOL_MOUNT_PATH / "source/photo/contestants"),
                    "chroma_db_path": str(VOL_MOUNT_PATH / "data/chroma_db"),
                    "processed_videos_dir": str(VOL_MOUNT_PATH / "processed_videos"),
                    "metadata_dir": str(VOL_MOUNT_PATH / "metadata"),
                },
            }
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

        self.processor = EnhancedVideoProcessor(config_path=config_path)
        print("✅ VideoProcessor ready")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @method()
    def process_video(
        self,
        video_name: str,
        similarity_threshold: float = 0.25,
    ) -> Dict[str, Any]:
        """Process a single video."""
        print(f"🎬 Processing: {video_name}")

        try:
            self.processor.set_similarity_threshold(similarity_threshold)
            result = self.processor.process_video_comprehensive(video_name)

            # Commit volume
            volume.commit()

            stats = result.get("stats", {})
            print(f"✅ Completed: {stats.get('total_faces_detected', 0)} faces detected")

            return {video_name: result}

        except Exception as e:
            print(f"❌ Failed: {e}")
            return {video_name: {"error": str(e)}}

    @method()
    def process_all(
        self,
        similarity_threshold: float = 0.25,
        force_reprocess: bool = False,
    ) -> Dict[str, Any]:
        """Process all videos."""
        print("🎬 Processing all videos...")

        self.processor.set_similarity_threshold(similarity_threshold)
        results = self.processor.batch_process_all_videos(force_reprocess)

        volume.commit()

        return results


# --- Upload Results Function ---

@app.function(
    image=modal_image,
    volumes={str(VOL_MOUNT_PATH): volume},
    secrets=[Secret.from_name("hf-secret")],
    timeout=7200,
)
def upload_to_huggingface(
    include_videos: bool = True,
    include_metadata: bool = True,
) -> Dict[str, Any]:
    """
    Upload processed results to HuggingFace.
    """
    from huggingface_hub import upload_file, upload_folder

    result = {
        "success": False,
        "uploaded": [],
        "errors": [],
    }

    try:
        token = os.environ.get("HF_TOKEN")
        print("☁️ Uploading results to HuggingFace...")

        # Upload metadata
        if include_metadata:
            metadata_dir = VOL_MOUNT_PATH / "metadata"
            if metadata_dir.exists():
                for file in metadata_dir.glob("*.json"):
                    upload_file(
                        path_or_fileobj=str(file),
                        path_in_repo=f"videos/metadata/{file.name}",
                        repo_id=HF_REPO_ID,
                        repo_type="dataset",
                        token=token,
                    )
                    result["uploaded"].append(f"metadata/{file.name}")
                    print(f"  📄 Uploaded: {file.name}")

        # Upload processed videos
        if include_videos:
            videos_dir = VOL_MOUNT_PATH / "processed_videos"
            if videos_dir.exists():
                for video in videos_dir.glob("*_annotated.mp4"):
                    print(f"  🎬 Uploading: {video.name} (may take a while...)")
                    upload_file(
                        path_or_fileobj=str(video),
                        path_in_repo=f"videos/processed/{video.name}",
                        repo_id=HF_REPO_ID,
                        repo_type="dataset",
                        token=token,
                    )
                    result["uploaded"].append(f"videos/{video.name}")
                    print(f"  ✅ Uploaded: {video.name}")

        result["success"] = True
        print(f"\n✅ Upload complete: {len(result['uploaded'])} files")

    except Exception as e:
        result["errors"].append(str(e))
        print(f"❌ Upload failed: {e}")

    return result


# --- Main Entry Point ---

@app.local_entrypoint()
def main(
    sync_from_hf: bool = False,
    update_embeddings: bool = False,
    process_videos: bool = False,
    upload_results: bool = False,
    full_pipeline: bool = False,
    single_video: str = "",
    similarity_threshold: float = 0.25,
    force_reprocess: bool = False,
):
    """
    Main entry point for HuggingFace-integrated processing.
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    console.print(Panel(
        "🚀 MV Face Recognition - HuggingFace Pipeline",
        title="[bold blue]Starting[/bold blue]"
    ))

    if full_pipeline:
        sync_from_hf = True
        update_embeddings = True
        process_videos = True
        upload_results = True

    # Step 1: Sync from HuggingFace
    if sync_from_hf:
        console.print("\n[bold]Step 1: Syncing from HuggingFace[/bold]")
        result = sync_from_huggingface.remote()
        if result["success"]:
            console.print(f"[green]✅ Downloaded {result['files_downloaded']} files[/green]")
        else:
            console.print(f"[red]❌ Sync failed: {result['errors']}[/red]")
            return

    # Step 2: Update embeddings from flagged faces
    if update_embeddings:
        console.print("\n[bold]Step 2: Updating embeddings from flagged faces[/bold]")
        result = update_embeddings_from_flagged.remote()
        if result["success"]:
            console.print(f"[green]✅ Updated {len(result['contestants_updated'])} contestants[/green]")
        else:
            console.print(f"[yellow]⚠️ Update issues: {result['errors']}[/yellow]")

    # Step 3: Process videos
    if process_videos:
        console.print("\n[bold]Step 3: Processing videos[/bold]")
        processor = VideoProcessor()

        if single_video:
            result = processor.process_video.remote(single_video, similarity_threshold)
        else:
            result = processor.process_all.remote(similarity_threshold, force_reprocess)

        # Print summary
        successful = sum(1 for v, r in result.items() if "error" not in r)
        failed = sum(1 for v, r in result.items() if "error" in r)
        console.print(f"[green]✅ Processed: {successful} successful, {failed} failed[/green]")

    # Step 4: Upload results
    if upload_results:
        console.print("\n[bold]Step 4: Uploading results to HuggingFace[/bold]")
        result = upload_to_huggingface.remote()
        if result["success"]:
            console.print(f"[green]✅ Uploaded {len(result['uploaded'])} files[/green]")
        else:
            console.print(f"[red]❌ Upload failed: {result['errors']}[/red]")

    console.print(Panel(
        "🎉 Pipeline complete!",
        title="[bold green]Done[/bold green]"
    ))


if __name__ == "__main__":
    print("Use: modal run modal_hf_processor.py --help")
