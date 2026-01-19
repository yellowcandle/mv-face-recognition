#!/usr/bin/env python3
"""
Validate face embeddings for dimension compatibility and freshness.

This script checks:
1. Embedding dimensions match expected (512-dim for current face_recognition)
2. Embeddings exist for all contestants
3. Photos are newer than embeddings (indicate potential updates needed)

Usage:
    python scripts/validate_embeddings.py --dir /path/to/contestants
    python scripts/validate_embeddings.py --check-only  # Don't regenerate
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Expected embedding dimensions for current face_recognition library
EXPECTED_EMBEDDING_DIMENSION = 512


@dataclass
class EmbeddingValidationResult:
    """Result of embedding validation."""
    all_valid: bool
    needs_regeneration: bool
    total_contestants: int
    valid_count: int
    dimension_mismatch_count: int
    missing_count: int
    photo_changed_count: int
    invalid_contestants: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "all_valid": self.all_valid,
            "needs_regeneration": self.needs_regeneration,
            "total_contestants": self.total_contestants,
            "valid_count": self.valid_count,
            "dimension_mismatch_count": self.dimension_mismatch_count,
            "missing_count": self.missing_count,
            "photo_changed_count": self.photo_changed_count,
            "invalid_contestants": self.invalid_contestants,
            "reason": self.reason,
        }


def get_embedding_dimensions(embedding_path: Path) -> Optional[int]:
    """
    Load embedding and return its dimension.

    Args:
        embedding_path: Path to .npy embedding file

    Returns:
        Embedding dimension (number of features) or None if invalid
    """
    try:
        embedding = np.load(str(embedding_path))
        # Handle both 1D and 2D arrays
        if embedding.ndim == 1:
            return int(embedding.shape[0])
        elif embedding.ndim == 2:
            return int(embedding.shape[1])
        else:
            logger.warning(f"Unexpected embedding shape: {embedding.shape}")
            return None
    except Exception as e:
        logger.debug(f"Failed to load {embedding_path}: {e}")
        return None


def check_embedding_compatibility(
    embedding_path: Path,
    expected_dim: int = EXPECTED_EMBEDDING_DIMENSION,
) -> Tuple[bool, Optional[int], Optional[int]]:
    """
    Check if embedding is compatible with current face_recognition library.

    Args:
        embedding_path: Path to embedding file
        expected_dim: Expected dimension (default: 512)

    Returns:
        Tuple of (is_compatible, actual_dim, expected_dim)
    """
    actual_dim = get_embedding_dimensions(embedding_path)
    if actual_dim is None:
        return False, None, expected_dim
    return actual_dim == expected_dim, actual_dim, expected_dim


def get_file_mtime(path: Path) -> Optional[float]:
    """Get modification time of file, return None if not found."""
    try:
        return path.stat().st_mtime if path.exists() else None
    except Exception:
        return None


def are_photos_newer_than_embedding(
    photo_dir: Path,
    embedding_path: Path,
) -> bool:
    """
    Check if any photo in directory is newer than embedding.

    Args:
        photo_dir: Directory containing contestant photos
        embedding_path: Path to embedding file

    Returns:
        True if photos are newer, False otherwise
    """
    embedding_mtime = get_file_mtime(embedding_path)
    if embedding_mtime is None:
        return False

    if not photo_dir.exists():
        return False

    # Check all photos in directory
    photo_extensions = {".jpg", ".jpeg", ".png"}
    for photo_path in photo_dir.glob("*"):
        if photo_path.suffix.lower() in photo_extensions:
            photo_mtime = get_file_mtime(photo_path)
            if photo_mtime is not None and photo_mtime > embedding_mtime:
                return True

    return False


def get_contestant_info(contestants_csv_path: Path) -> Dict[str, Dict[str, str]]:
    """
    Load contestant information from CSV.

    Args:
        contestants_csv_path: Path to contestant_info.csv

    Returns:
        Dict mapping contestant_id to info dict with name, nickname, age
    """
    contestants = {}
    try:
        df = pd.read_csv(contestants_csv_path)
        for _, row in df.iterrows():
            contestant_id = str(row["編號"])
            contestants[contestant_id] = {
                "id": contestant_id,
                "name": row["姓名"],
                "nickname": row["暱稱"],
                "age": str(row["年齡"]),
            }
        logger.info(f"Loaded {len(contestants)} contestants from CSV")
    except Exception as e:
        logger.error(f"Failed to load contestants CSV: {e}")

    return contestants


def validate_all_embeddings(
    photo_base_dir: Path,
    embeddings_dir: Path,
    contestants_csv_path: Optional[Path] = None,
    expected_dim: int = EXPECTED_EMBEDDING_DIMENSION,
    check_photo_changes: bool = True,
) -> EmbeddingValidationResult:
    """
    Validate all embeddings in directory.

    Args:
        photo_base_dir: Base directory containing photos and embeddings
        embeddings_dir: Directory containing embedding files
        contestants_csv_path: Path to contestant_info.csv (optional)
        expected_dim: Expected embedding dimension
        check_photo_changes: Whether to check if photos are newer than embeddings

    Returns:
        EmbeddingValidationResult with validation details
    """
    invalid_contestants = []
    dimension_mismatch_count = 0
    missing_count = 0
    photo_changed_count = 0
    valid_count = 0

    # Load contestant info if CSV provided
    contestants_info = {}
    if contestants_csv_path and contestants_csv_path.exists():
        contestants_info = get_contestant_info(contestants_csv_path)

    # Get list of expected embeddings from contestants or files
    if contestants_info:
        # Use contestants from CSV as source of truth
        expected_contestants = set(contestants_info.keys())
        embedding_files = list(embeddings_dir.glob("*_embedding.npy"))

        # Build mapping from nickname to contestant_id
        nickname_to_id = {
            info["nickname"]: cid for cid, info in contestants_info.items()
        }

        for contestant_id in expected_contestants:
            info = contestants_info[contestant_id]
            nickname = info.get("nickname", "")
            embedding_path = embeddings_dir / f"{nickname}_embedding.npy"

            if not embedding_path.exists():
                missing_count += 1
                invalid_contestants.append({
                    "contestant_id": contestant_id,
                    "nickname": nickname,
                    "reason": "missing",
                    "path": str(embedding_path),
                })
            else:
                # Check dimension
                compatible, actual_dim, _ = check_embedding_compatibility(
                    embedding_path, expected_dim
                )
                if not compatible:
                    dimension_mismatch_count += 1
                    invalid_contestants.append({
                        "contestant_id": contestant_id,
                        "nickname": nickname,
                        "reason": "dimension_mismatch",
                        "path": str(embedding_path),
                        "actual_dim": actual_dim,
                        "expected_dim": expected_dim,
                    })
                else:
                    # Check if photos are newer
                    if check_photo_changes:
                        photo_dir = photo_base_dir / "photos" / f"contestant_{contestant_id}"
                        if are_photos_newer_than_embedding(photo_dir, embedding_path):
                            photo_changed_count += 1
                            invalid_contestants.append({
                                "contestant_id": contestant_id,
                                "nickname": nickname,
                                "reason": "photo_changed",
                                "path": str(embedding_path),
                            })
                        else:
                            valid_count += 1
                    else:
                        valid_count += 1

    total = valid_count + dimension_mismatch_count + missing_count + photo_changed_count

    # Determine overall status and reason
    needs_regeneration = dimension_mismatch_count > 0 or missing_count > 0 or photo_changed_count > 0

    if dimension_mismatch_count > 0 and missing_count == 0 and photo_changed_count == 0:
        reason = "dimension_mismatch"
    elif missing_count > 0 and dimension_mismatch_count == 0 and photo_changed_count == 0:
        reason = "missing"
    elif photo_changed_count > 0 and dimension_mismatch_count == 0 and missing_count == 0:
        reason = "photo_changed"
    elif dimension_mismatch_count > 0 or missing_count > 0:
        reason = "mixed"
    elif photo_changed_count > 0:
        reason = "photo_changed"
    else:
        reason = "valid"

    result = EmbeddingValidationResult(
        all_valid=(needs_regeneration == False),
        needs_regeneration=needs_regeneration,
        total_contestants=total,
        valid_count=valid_count,
        dimension_mismatch_count=dimension_mismatch_count,
        missing_count=missing_count,
        photo_changed_count=photo_changed_count,
        invalid_contestants=invalid_contestants,
        reason=reason,
    )

    # Log summary
    logger.info(f"Validation Summary:")
    logger.info(f"  Total contestants: {result.total_contestants}")
    logger.info(f"  Valid embeddings: {result.valid_count}")
    logger.info(f"  Dimension mismatch: {result.dimension_mismatch_count}")
    logger.info(f"  Missing embeddings: {result.missing_count}")
    logger.info(f"  Photo changes detected: {result.photo_changed_count}")
    logger.info(f"  Needs regeneration: {result.needs_regeneration} ({result.reason})")

    return result


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Validate face embeddings for dimension compatibility and freshness"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("source/photo/contestants"),
        help="Base directory containing photos and embeddings",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("metadata/contestant_info.csv"),
        help="Path to contestant_info.csv",
    )
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=None,
        help="Directory containing embeddings (default: same as --dir)",
    )
    parser.add_argument(
        "--expected-dim",
        type=int,
        default=EXPECTED_EMBEDDING_DIMENSION,
        help=f"Expected embedding dimension (default: {EXPECTED_EMBEDDING_DIMENSION})",
    )
    parser.add_argument(
        "--skip-photo-check",
        action="store_true",
        help="Skip checking if photos are newer than embeddings",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    photo_base_dir = args.dir.resolve()
    embeddings_dir = (args.embeddings or args.dir).resolve()
    csv_path = args.csv.resolve()

    if not photo_base_dir.exists():
        logger.error(f"Photo directory not found: {photo_base_dir}")
        sys.exit(1)

    if not embeddings_dir.exists():
        logger.warning(f"Embeddings directory not found: {embeddings_dir}")
        # Create it if it doesn't exist
        embeddings_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created embeddings directory: {embeddings_dir}")

    result = validate_all_embeddings(
        photo_base_dir=photo_base_dir,
        embeddings_dir=embeddings_dir,
        contestants_csv_path=csv_path if csv_path.exists() else None,
        expected_dim=args.expected_dim,
        check_photo_changes=not args.skip_photo_check,
    )

    if args.json:
        import json
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.needs_regeneration:
            logger.info(f"\n⚠️  Embeddings need regeneration: {result.reason}")
            logger.info(f"   Run regeneration to fix {len(result.invalid_contestants)} contestants")
            sys.exit(1)
        else:
            logger.info(f"\n✅ All embeddings are valid")
            sys.exit(0)


if __name__ == "__main__":
    main()
