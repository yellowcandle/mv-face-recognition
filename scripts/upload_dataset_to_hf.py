#!/usr/bin/env python3
"""
Upload contestant dataset to HuggingFace XET.

This script uploads the complete contestant dataset (photos, embeddings, metadata)
to HuggingFace XET storage for efficient large file management.

Usage:
    python scripts/upload_dataset_to_hf.py --upload        # Upload all data
    python scripts/upload_dataset_to_hf.py --download-only # Download to verify
    python scripts/upload_dataset_to_hf.py --verify        # Verify existing upload
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.integrations.huggingface_xet import HuggingFaceDataset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_prerequisites(
    csv_path: str,
    photos_dir: str,
    embeddings_dir: str,
) -> Dict[str, Any]:
    """
    Validate that all prerequisites are met before upload.

    Returns:
        Dictionary with validation results
    """
    results: Dict[str, Any] = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {},
    }

    logger.info("🔍 Validating prerequisites...")

    # Check HuggingFace token (environment variable or CLI login)
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        # Try to use CLI-cached credentials
        try:
            from huggingface_hub import HfApi
            api = HfApi()
            # This will use cached credentials if available
            whoami = api.whoami()
            logger.info(f"  ✅ HuggingFace CLI authenticated as: {whoami['name']}")
        except Exception as e:
            results["valid"] = False
            results["errors"].append(
                "HuggingFace authentication required. Run: huggingface-cli login"
            )
    else:
        logger.info("  ✅ HuggingFace token found")

    # Check contestant CSV
    if not os.path.exists(csv_path):
        results["valid"] = False
        results["errors"].append(f"Contestant CSV not found: {csv_path}")
    else:
        logger.info(f"  ✅ Contestant CSV found: {csv_path}")
        # Count contestants
        with open(csv_path, "r", encoding="utf-8") as f:
            # Skip header line
            contestant_count = sum(1 for line in f) - 1
            results["stats"]["contestants"] = contestant_count
            logger.info(f"     Found {contestant_count} contestants")

    # Check photos directory
    if not os.path.exists(photos_dir):
        results["valid"] = False
        results["errors"].append(f"Photos directory not found: {photos_dir}")
    else:
        photos_path = Path(photos_dir)
        photo_files = list(photos_path.rglob("*.jpg")) + list(photos_path.rglob("*.png"))
        photo_files = [f for f in photo_files if not f.name.endswith("_embedding.npy")]
        results["stats"]["photos"] = len(photo_files)

        # Calculate total size
        total_size = sum(f.stat().st_size for f in photo_files)
        results["stats"]["photos_size_mb"] = total_size / (1024 * 1024)

        logger.info(f"  ✅ Photos directory found: {photos_dir}")
        logger.info(f"     {len(photo_files)} photos ({total_size / (1024 * 1024):.2f} MB)")

    # Check embeddings directory
    if not os.path.exists(embeddings_dir):
        results["warnings"].append(f"Embeddings directory not found: {embeddings_dir}")
        logger.info(f"  ⚠️  Embeddings directory not found: {embeddings_dir}")
        results["stats"]["embeddings"] = 0
    else:
        embeddings_path = Path(embeddings_dir)
        embedding_files = list(embeddings_path.rglob("*_embedding.npy"))
        results["stats"]["embeddings"] = len(embedding_files)
        logger.info(f"  ✅ Embeddings directory found: {embeddings_dir}")
        logger.info(f"     {len(embedding_files)} embedding files")

    return results


def upload_dataset(
    dataset: HuggingFaceDataset,
    csv_path: str,
    photos_dir: str,
    embeddings_dir: str,
) -> Dict[str, Any]:
    """
    Upload the complete dataset to HuggingFace.

    Returns:
        Dictionary with upload results
    """
    results: Dict[str, Any] = {
        "metadata_uploaded": False,
        "embeddings_uploaded": False,
        "photos_uploaded": False,
        "stats": {},
    }

    logger.info("\n" + "=" * 60)
    logger.info("📤 STARTING DATASET UPLOAD TO HUGGINGFACE XET")
    logger.info("=" * 60)

    # Step 1: Upload metadata (smallest, validates connectivity)
    logger.info("\n📋 Step 1/3: Uploading contestant metadata...")
    try:
        success = dataset.upload_contestant_data(csv_path)
        results["metadata_uploaded"] = success
        if success:
            logger.info("✅ Metadata upload complete")
        else:
            logger.info("❌ Metadata upload failed")
            return results
    except Exception as e:
        logger.info(f"❌ Metadata upload failed: {e}")
        return results

    # Step 2: Upload embeddings (if available)
    logger.info("\n🧠 Step 2/3: Uploading face embeddings...")
    try:
        if os.path.exists(embeddings_dir):
            embedding_stats = dataset.upload_embeddings(embeddings_dir)
            results["stats"]["embeddings"] = embedding_stats
            results["embeddings_uploaded"] = embedding_stats["uploaded"] > 0
            logger.info(f"✅ Embeddings upload complete")
        else:
            logger.info("⚠️  Embeddings directory not found, skipping")
            results["embeddings_uploaded"] = True  # Not a failure
    except Exception as e:
        logger.info(f"❌ Embeddings upload failed: {e}")
        # Continue to photos even if embeddings fail

    # Step 3: Upload photos (largest files)
    logger.info("\n📸 Step 3/3: Uploading contestant photos...")
    try:
        photo_stats = dataset.upload_contestant_photos(photos_dir)
        results["stats"]["photos"] = photo_stats
        results["photos_uploaded"] = photo_stats["uploaded"] > 0
        logger.info(f"✅ Photos upload complete")
    except Exception as e:
        logger.info(f"❌ Photos upload failed: {e}")
        return results

    return results


def verify_upload(
    dataset: HuggingFaceDataset,
    csv_path: str,
    photos_dir: str,
    sample_count: int = 5,
) -> Dict[str, Any]:
    """
    Verify uploaded data by downloading samples and comparing checksums.

    Returns:
        Dictionary with verification results
    """
    results: Dict[str, Any] = {
        "verified": False,
        "samples_checked": 0,
        "samples_matched": 0,
        "errors": [],
    }

    logger.info("\n" + "=" * 60)
    logger.info("🔍 VERIFYING UPLOAD")
    logger.info("=" * 60)

    try:
        # Get list of photos to verify
        photos_path = Path(photos_dir)
        photo_files = list(photos_path.rglob("*.jpg"))[:sample_count]

        logger.info(f"\n📊 Verifying {len(photo_files)} sample photos...")

        for photo_file in photo_files:
            results["samples_checked"] += 1

            # Calculate local hash
            local_hash = calculate_file_hash(str(photo_file))

            # Extract path info
            relative_path = photo_file.relative_to(photos_path)
            parts = list(relative_path.parts)
            contestant_dir = parts[0]
            filename = parts[-1]

            # Download from HuggingFace
            remote_path = f"photos/contestant_{contestant_dir}/{filename}"

            try:
                from huggingface_hub import hf_hub_download

                local_downloaded = hf_hub_download(
                    repo_id=dataset.repo_id,
                    repo_type="dataset",
                    filename=remote_path,
                    token=dataset.token,
                )

                # Calculate downloaded hash
                remote_hash = calculate_file_hash(local_downloaded)

                if local_hash == remote_hash:
                    results["samples_matched"] += 1
                    logger.info(f"  ✅ Verified: {remote_path}")
                else:
                    results["errors"].append(f"Hash mismatch: {remote_path}")
                    logger.info(f"  ❌ Hash mismatch: {remote_path}")

            except Exception as e:
                results["errors"].append(f"Download failed: {remote_path} - {str(e)}")
                logger.info(f"  ❌ Download failed: {remote_path} - {e}")

        # Check if all samples matched
        results["verified"] = (
            results["samples_checked"] == results["samples_matched"]
            and results["samples_checked"] > 0
        )

        logger.info(f"\n📊 Verification Summary:")
        logger.info(f"  • Samples checked: {results['samples_checked']}")
        logger.info(f"  • Samples matched: {results['samples_matched']}")
        logger.info(f"  • Errors: {len(results['errors'])}")

        if results["verified"]:
            logger.info("  ✅ All samples verified successfully!")
        else:
            logger.info("  ❌ Verification failed!")

    except Exception as e:
        logger.info(f"❌ Verification failed: {e}")
        results["errors"].append(str(e))

    return results


def download_dataset(
    dataset: HuggingFaceDataset,
    target_dir: str,
) -> Dict[str, Any]:
    """
    Download the dataset from HuggingFace for verification.

    Returns:
        Dictionary with download results
    """
    logger.info("\n" + "=" * 60)
    logger.info("📥 DOWNLOADING DATASET FROM HUGGINGFACE")
    logger.info("=" * 60)

    try:
        stats = dataset.download_dataset(
            target_dir=target_dir,
            include_videos=False,
            include_flagged=False,
        )

        logger.info(f"\n✅ Download complete:")
        logger.info(f"  • Files downloaded: {stats['downloaded_files']}")
        logger.info(f"  • Total size: {stats['total_size_mb']:.2f} MB")

        return stats

    except Exception as e:
        logger.info(f"❌ Download failed: {e}")
        return {"error": str(e)}


def print_summary(
    upload_results: Dict[str, Any],
    verify_results: Dict[str, Any],
    validation: Dict[str, Any],
):
    """Print final summary report."""
    logger.info("\n" + "=" * 60)
    logger.info("📊 UPLOAD SUMMARY REPORT")
    logger.info("=" * 60)

    # Dataset stats
    logger.info("\n📈 Dataset Statistics:")
    if "stats" in validation:
        stats = validation["stats"]
        if "contestants" in stats:
            logger.info(f"  • Contestants: {stats['contestants']}")
        if "photos" in stats:
            logger.info(f"  • Photos: {stats['photos']} ({stats.get('photos_size_mb', 0):.2f} MB)")
        if "embeddings" in stats:
            logger.info(f"  • Embeddings: {stats['embeddings']}")

    # Upload results
    logger.info("\n📤 Upload Results:")
    logger.info(f"  • Metadata: {'✅ Uploaded' if upload_results.get('metadata_uploaded') else '❌ Failed'}")
    logger.info(f"  • Embeddings: {'✅ Uploaded' if upload_results.get('embeddings_uploaded') else '❌ Failed'}")
    logger.info(f"  • Photos: {'✅ Uploaded' if upload_results.get('photos_uploaded') else '❌ Failed'}")

    if "stats" in upload_results and "photos" in upload_results["stats"]:
        photo_stats = upload_results["stats"]["photos"]
        logger.info(f"\n📸 Photo Upload Details:")
        logger.info(f"  • Uploaded: {photo_stats['uploaded']}")
        logger.info(f"  • Failed: {photo_stats['failed']}")
        logger.info(f"  • Total size: {photo_stats['total_size_mb']:.2f} MB")

    # Verification results
    if verify_results:
        logger.info(f"\n🔍 Verification:")
        logger.info(f"  • Status: {'✅ Passed' if verify_results.get('verified') else '❌ Failed'}")
        logger.info(f"  • Samples checked: {verify_results.get('samples_checked', 0)}")
        logger.info(f"  • Samples matched: {verify_results.get('samples_matched', 0)}")

    # Final status
    logger.info("\n" + "=" * 60)
    all_success = (
        upload_results.get("metadata_uploaded", False)
        and upload_results.get("embeddings_uploaded", False)
        and upload_results.get("photos_uploaded", False)
    )

    if all_success:
        logger.info("✅ DATASET UPLOAD SUCCESSFUL!")
        logger.info("\nNext steps:")
        logger.info("1. Visit: https://huggingface.co/datasets/yellowcandle/mv-face-recognition-data")
        logger.info("2. Verify the uploaded files in the web interface")
        logger.info("3. Create a backup branch before removing from Git:")
        logger.info("   git checkout -b backup-before-hf-migration")
        logger.info("   git push origin backup-before-hf-migration")
    else:
        logger.info("❌ UPLOAD INCOMPLETE - Please check errors above")

    logger.info("=" * 60)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Upload contestant dataset to HuggingFace XET",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload the complete dataset to HuggingFace",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download dataset from HuggingFace (for verification)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify uploaded data by comparing checksums",
    )
    parser.add_argument(
        "--csv-path",
        default="metadata/contestant_info.csv",
        help="Path to contestant CSV file (default: metadata/contestant_info.csv)",
    )
    parser.add_argument(
        "--photos-dir",
        default="source/photo/contestants",
        help="Path to photos directory (default: source/photo/contestants)",
    )
    parser.add_argument(
        "--embeddings-dir",
        default="source/photo/contestants",
        help="Path to embeddings directory (default: source/photo/contestants)",
    )
    parser.add_argument(
        "--download-dir",
        default="./hf_dataset_download",
        help="Directory for download (default: ./hf_dataset_download)",
    )

    args = parser.parse_args()

    # Initialize dataset
    try:
        dataset = HuggingFaceDataset(
            repo_id="yellowcandle/mv-face-recognition-data",
            token=os.getenv("HF_TOKEN"),
        )
        logger.info(f"✅ Connected to HuggingFace repository: {dataset.repo_id}")

        # Ensure repository exists
        if not dataset.ensure_repo_exists():
            logger.info("❌ Failed to access HuggingFace repository")
            return 1

    except Exception as e:
        logger.info(f"❌ Failed to initialize HuggingFace dataset: {e}")
        return 1

    # Handle download-only mode
    if args.download_only:
        download_dataset(dataset, args.download_dir)
        return 0

    # Validate prerequisites
    validation = validate_prerequisites(
        args.csv_path,
        args.photos_dir,
        args.embeddings_dir,
    )

    if not validation["valid"]:
        logger.info("\n❌ Validation failed:")
        for error in validation["errors"]:
            logger.info(f"  • {error}")
        return 1

    upload_results: Dict[str, Any] = {}
    verify_results: Dict[str, Any] = {}

    # Upload if requested
    if args.upload:
        upload_results = upload_dataset(
            dataset,
            args.csv_path,
            args.photos_dir,
            args.embeddings_dir,
        )

        # Auto-verify after upload
        if upload_results.get("photos_uploaded"):
            verify_results = verify_upload(
                dataset,
                args.csv_path,
                args.photos_dir,
                sample_count=5,
            )

    # Verify only if requested
    elif args.verify:
        verify_results = verify_upload(
            dataset,
            args.csv_path,
            args.photos_dir,
            sample_count=10,
        )

    # Print summary
    if upload_results or verify_results:
        print_summary(upload_results, verify_results, validation)

    return 0


if __name__ == "__main__":
    sys.exit(main())
