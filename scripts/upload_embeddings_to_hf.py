#!/usr/bin/env python3
"""
Upload regenerated face embeddings to HuggingFace XET storage.

This script uploads embedding files (.npy) to the HuggingFace dataset repository,
creating an embedding manifest to track dimensions and generation timestamps.

Usage:
    python scripts/upload_embeddings_to_hf.py --dir /path/to/embeddings
    python scripts/upload_embeddings_to_hf.py --dir /path/to/embeddings --repo-id custom/repo
    python scripts/upload_embeddings_to_hf.py --dir /path/to/embeddings --dry-run
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast
import shutil

try:
    from huggingface_hub import HfApi, hf_hub_download
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
    print("Warning: huggingface_hub not installed. Install with: pip install huggingface_hub")

if TYPE_CHECKING:
    from huggingface_hub import HfApi, hf_hub_download

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_REPO_ID = "yellowcandle/mv-face-recognition-data"


@dataclass
class HuggingFaceUploadResult:
    """Result of HuggingFace upload operation."""
    success: bool
    files_uploaded: int
    files_failed: int
    failed_files: List[Dict[str, str]] = field(default_factory=list)
    repo_url: Optional[str] = None
    duration_seconds: float = 0.0
    manifest_created: bool = False


def get_embedding_dimension(embedding_path: Path) -> Optional[int]:
    """Get the dimension of an embedding file."""
    try:
        embedding = np.load(str(embedding_path))
        if embedding.ndim == 1:
            return int(embedding.shape[0])
        elif embedding.ndim == 2:
            return int(embedding.shape[1])
        return None
    except Exception as e:
        logger.debug(f"Failed to load {embedding_path}: {e}")
        return None


def create_embedding_manifest(
    embeddings_dir: Path,
    output_path: Path,
    dimension: int = 512,
) -> Dict[str, Any]:
    """
    Create a manifest file tracking embedding metadata.

    Args:
        embeddings_dir: Directory containing embedding files
        output_path: Path to save manifest JSON
        dimension: Embedding dimension

    Returns:
        Manifest dictionary
    """
    manifest: Dict[str, Any] = {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dimension": dimension,
        "embeddings": {},
    }

    for embedding_path in embeddings_dir.glob("*_embedding.npy"):
        nickname = embedding_path.stem.replace("_embedding", "")
        dim = get_embedding_dimension(embedding_path)

        manifest["embeddings"][nickname] = {
            "filename": embedding_path.name,
            "dimension": dim or dimension,
            "mtime": embedding_path.stat().st_mtime,
        }

    # Write manifest
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Created embedding manifest: {output_path}")
    return manifest


def upload_embeddings_to_huggingface(
    embeddings_dir: Path,
    repo_id: str = DEFAULT_REPO_ID,
    token: Optional[str] = None,
    create_manifest: bool = True,
    manifest_dimension: int = 512,
) -> HuggingFaceUploadResult:
    """
    Upload embedding files to HuggingFace dataset repository.

    Uses upload_folder() for batch uploads which handles the new commit API
    and rate limiting automatically.

    Args:
        embeddings_dir: Directory containing .npy embedding files
        repo_id: HuggingFace repository ID (user/repo-name)
        token: HuggingFace API token (uses HF_TOKEN env var if not provided)
        create_manifest: Whether to create and upload embedding manifest
        manifest_dimension: Dimension to record in manifest

    Returns:
        HuggingFaceUploadResult with upload details
    """
    if not HF_AVAILABLE:
        logger.error("huggingface_hub is not installed")
        return HuggingFaceUploadResult(
            success=False,
            files_uploaded=0,
            files_failed=0,
            failed_files=[{"path": str(embeddings_dir), "error": "huggingface_hub not installed"}],
        )

    from huggingface_hub import HfApi
    import shutil

    start_time = time.time()
    failed_files = []
    files_uploaded = 0

    # Get token - try explicit token, env var, then CLI cache
    token_str: Optional[str] = None
    if token is not None and isinstance(token, str):
        token_str = token
        logger.debug("Using token from parameter")
    else:
        raw_env = os.getenv("HF_TOKEN")
        if raw_env is not None and isinstance(raw_env, str):
            token_str = raw_env
            logger.debug("Using token from HF_TOKEN environment variable")

    # Initialize API - will use CLI cached token if token_str is None
    api = HfApi(token=token_str)

    # Verify we have a valid token
    try:
        # This will use CLI cache if token_str is None
        whoami_info = api.whoami()
        logger.info(f"Authenticated as: {whoami_info.get('name', 'unknown')}")
    except Exception as e:
        logger.error(f"No HuggingFace token found or authentication failed: {e}")
        return HuggingFaceUploadResult(
            success=False,
            files_uploaded=0,
            files_failed=0,
            failed_files=[{"path": str(embeddings_dir), "error": f"Authentication failed: {e}"}],
        )

    # Get embedding files
    embedding_files = list(embeddings_dir.glob("*_embedding.npy"))
    if not embedding_files:
        logger.warning(f"No embedding files found in {embeddings_dir}")
        return HuggingFaceUploadResult(
            success=True,
            files_uploaded=0,
            files_failed=0,
        )

    logger.info(f"Found {len(embedding_files)} embedding files to upload")

    # Create a temporary directory structure for upload
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy embeddings to temp directory with correct structure
        embeddings_temp_dir = temp_path / "embeddings"
        embeddings_temp_dir.mkdir()

        for embedding_path in embedding_files:
            try:
                shutil.copy2(embedding_path, embeddings_temp_dir / embedding_path.name)
            except Exception as e:
                logger.warning(f"Failed to copy {embedding_path.name} to temp: {e}")

        # Create manifest if requested
        manifest_created = False
        manifest_temp_path = None
        if create_manifest:
            manifest_path = embeddings_dir / "embedding_manifest.json"
            create_embedding_manifest(
                embeddings_dir=embeddings_dir,
                output_path=manifest_path,
                dimension=manifest_dimension,
            )
            manifest_temp_path = temp_path / "metadata"
            manifest_temp_path.mkdir()
            shutil.copy2(manifest_path, manifest_temp_path / "embedding_manifest.json")

        # Upload using upload_folder with PR creation (works with limited permissions)
        try:
            logger.info(f"Uploading embeddings to {repo_id} via Pull Request...")

            # Use upload_folder to create a single PR for all files
            commit_message = f"Update {len(embedding_files)} face recognition embeddings (auto-generated)"
            pr_url = api.upload_folder(
                folder_path=str(temp_path),
                repo_id=repo_id,
                repo_type="dataset",
                commit_message=commit_message,
                create_pr=True,  # Create PR instead of pushing to main
            )

            files_uploaded = len(embedding_files)
            if create_manifest:
                manifest_created = True

            logger.info(f"✅ Uploaded {files_uploaded} embedding files")
            if manifest_created:
                logger.info("✅ Uploaded embedding manifest")
            logger.info(f"📝 Pull Request created: {pr_url}")

        except Exception as e:
            logger.error(f"Failed to upload embeddings: {e}")
            if not failed_files:
                failed_files = [{"path": str(emb), "error": str(e)} for emb in embedding_files]

    duration = time.time() - start_time
    repo_url = f"https://huggingface.co/datasets/{repo_id}"

    result = HuggingFaceUploadResult(
        success=files_uploaded > 0,
        files_uploaded=files_uploaded,
        files_failed=len(failed_files),
        failed_files=failed_files,
        repo_url=repo_url,
        duration_seconds=duration,
        manifest_created=manifest_created,
    )

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Upload Summary:")
    logger.info(f"  Files uploaded: {result.files_uploaded}")
    logger.info(f"  Files failed: {result.files_failed}")
    logger.info(f"  Manifest created: {result.manifest_created}")
    logger.info(f"  Repository: {repo_id}")
    logger.info(f"  Duration: {result.duration_seconds:.2f}s")
    logger.info(f"{'=' * 60}\n")

    return result


def verify_uploaded_embeddings(
    repo_id: str = DEFAULT_REPO_ID,
    sample_count: int = 5,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Verify uploaded embeddings by downloading samples and checking dimensions.

    Args:
        repo_id: HuggingFace repository ID
        sample_count: Number of samples to verify
        token: HuggingFace API token

    Returns:
        Dictionary with verification results
    """
    if not HF_AVAILABLE:
        return {"verified": False, "error": "huggingface_hub not installed"}

    token = token or os.getenv("HF_TOKEN")
    if not token or not isinstance(token, str):
        try:
            from huggingface_hub import HfApi
            api_inst = HfApi()
            raw_token = api_inst.token
            if raw_token is None or not isinstance(raw_token, str):
                return {"verified": False, "error": "No valid token found"}
            token = raw_token
        except Exception as e:
            return {"verified": False, "error": f"No token: {e}"}

    results: Dict[str, Any] = {
        "verified": True,
        "samples_checked": 0,
        "dimension_matched": 0,
        "errors": [],
    }

    try:
        # List files in embeddings directory
        api = HfApi(token=token)
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
        embedding_files = [f for f in files if f.startswith("embeddings/") and f.endswith(".npy")]

        for filename in embedding_files[:sample_count]:
            try:
                local_path = hf_hub_download(
                    repo_id=repo_id,
                    repo_type="dataset",
                    filename=filename,
                    token=token,
                )

                dim = get_embedding_dimension(Path(local_path))
                results["samples_checked"] += 1
                if dim == 512:
                    results["dimension_matched"] += 1
                else:
                    results["errors"].append({
                        "file": filename,
                        "issue": f"Dimension {dim}, expected 512",
                    })

            except Exception as e:
                results["errors"].append({"file": filename, "error": str(e)})

    except Exception as e:
        results["verified"] = False
        results["error"] = str(e)

    return results


def main() -> None:
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Upload regenerated face embeddings to HuggingFace XET storage"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="Directory containing embedding files to upload",
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        default=DEFAULT_REPO_ID,
        help="HuggingFace repository ID (default: yellowcandle/mv-face-recognition-data)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="HuggingFace API token (uses HF_TOKEN env var if not provided)",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Skip creating and uploading embedding manifest",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=512,
        help="Embedding dimension to record in manifest (default: 512)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify uploaded embeddings after upload",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )

    args = parser.parse_args()

    embeddings_dir = args.dir.resolve()
    if not embeddings_dir.exists():
        logger.error(f"Embeddings directory not found: {embeddings_dir}")
        sys.exit(1)

    if args.dry_run:
        embedding_files = list(embeddings_dir.glob("*_embedding.npy"))
        logger.info(f"Would upload {len(embedding_files)} files:")
        for f in embedding_files:
            logger.info(f"  - {f.name}")
        sys.exit(0)

    result = upload_embeddings_to_huggingface(
        embeddings_dir=embeddings_dir,
        repo_id=args.repo_id,
        token=args.token,
        create_manifest=not args.no_manifest,
        manifest_dimension=args.dimension,
    )

    if args.verify and result.success:
        logger.info("Verifying uploaded embeddings...")
        verify_result = verify_uploaded_embeddings(repo_id=args.repo_id, token=args.token)
        if verify_result.get("verified"):
            logger.info(
                f"✅ Verified {verify_result['samples_checked']} samples, "
                f"{verify_result['dimension_matched']} with correct dimension"
            )
        else:
            logger.warning(f"Verification issues: {verify_result.get('errors', [])}")

    if result.success:
        logger.info(f"✅ Upload complete: {result.files_uploaded} files to {result.repo_url}")
        sys.exit(0)
    else:
        logger.error(f"❌ Upload failed: {result.failed_files}")
        sys.exit(1)


if __name__ == "__main__":
    main()
