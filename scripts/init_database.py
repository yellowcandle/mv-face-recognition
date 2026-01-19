#!/usr/bin/env python3
"""
Database initialization script for MV Face Recognition system.

This script:
1. Loads contestant data from CSV
2. Initializes ChromaDB collection
3. Loads face embeddings from photos
4. Verifies data integrity
5. Syncs with HuggingFace XET (optional)

Usage:
    python scripts/init_database.py                    # Local initialization only
    python scripts/init_database.py --sync-hf          # Also sync with HuggingFace
    python scripts/init_database.py --verify           # Verify only, no changes
"""

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Initialize and verify the face recognition database."""

    def __init__(
        self,
        contestant_csv: str = "metadata/contestant_info.csv",
        contestant_photos_dir: str = "source/photo/contestants",
        chroma_db_path: str = ".chroma_db",
    ):
        """Initialize database initializer."""
        self.contestant_csv = Path(contestant_csv)
        self.contestant_photos_dir = Path(contestant_photos_dir)
        self.chroma_db_path = Path(chroma_db_path)

        # Load contestant data
        self.contestants: Dict[int, Dict[str, str]] = {}
        self.embeddings: Dict[int, np.ndarray] = {}

        logger.info("Database initializer created")

    def load_contestant_csv(self) -> bool:
        """Load contestant data from CSV file."""
        if not self.contestant_csv.exists():
            logger.error(f"Contestant CSV not found: {self.contestant_csv}")
            return False

        try:
            with open(self.contestant_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    contestant_id = int(row["編號"])
                    self.contestants[contestant_id] = {
                        "name": row["姓名"],
                        "nickname": row["暱稱"],
                        "age": row["年齡"],
                    }

            logger.info(f"✅ Loaded {len(self.contestants)} contestants from CSV")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load contestant CSV: {e}")
            return False

    def load_embeddings_from_photos(self) -> bool:
        """Load face embeddings from contestant photos."""
        if not self.contestant_photos_dir.exists():
            logger.error(f"Contestant photos directory not found: {self.contestant_photos_dir}")
            return False

        try:
            # Build nickname to ID mapping
            nickname_to_id = {}
            for contestant_id, info in self.contestants.items():
                nickname = info["nickname"]
                nickname_to_id[nickname] = contestant_id

            # Find all embedding files
            embedding_files = list(self.contestant_photos_dir.glob("*_embedding.npy"))
            logger.info(f"Found {len(embedding_files)} embedding files")

            loaded_count = 0
            for embedding_file in embedding_files:
                try:
                    # Extract nickname from filename (remove "_embedding.npy")
                    nickname = embedding_file.stem.replace("_embedding", "")
                    
                    # Look up contestant ID by nickname
                    if nickname in nickname_to_id:
                        contestant_id = nickname_to_id[nickname]
                        embedding = np.load(embedding_file)
                        self.embeddings[contestant_id] = embedding
                        loaded_count += 1
                except Exception as e:
                    logger.debug(f"Skipping embedding file {embedding_file}: {e}")
                    continue

            logger.info(f"✅ Loaded {loaded_count} embeddings from photos")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load embeddings: {e}")
            return False

    def verify_data_consistency(self) -> Tuple[bool, Dict[str, any]]:
        """Verify data consistency between contestants and embeddings."""
        stats = {
            "total_contestants": len(self.contestants),
            "total_embeddings": len(self.embeddings),
            "missing_embeddings": [],
            "orphan_embeddings": [],
            "embedding_shapes": {},
        }

        # Check for missing embeddings
        for contestant_id in self.contestants:
            if contestant_id not in self.embeddings:
                stats["missing_embeddings"].append(contestant_id)

        # Check for orphan embeddings (no contestant info)
        for embedding_id in self.embeddings:
            if embedding_id not in self.contestants:
                stats["orphan_embeddings"].append(embedding_id)

        # Check embedding shapes
        for contestant_id, embedding in self.embeddings.items():
            shape = embedding.shape
            if shape not in stats["embedding_shapes"]:
                stats["embedding_shapes"][shape] = 0
            stats["embedding_shapes"][shape] += 1

        # Log verification results
        logger.info(f"\n📊 Data Consistency Report:")
        logger.info(f"   Total contestants: {stats['total_contestants']}")
        logger.info(f"   Total embeddings: {stats['total_embeddings']}")

        if stats["missing_embeddings"]:
            logger.warning(
                f"   ⚠️  Missing embeddings for {len(stats['missing_embeddings'])} contestants: {stats['missing_embeddings'][:5]}..."
            )
        else:
            logger.info(f"   ✅ All contestants have embeddings")

        if stats["orphan_embeddings"]:
            logger.warning(
                f"   ⚠️  {len(stats['orphan_embeddings'])} orphan embeddings found"
            )
        else:
            logger.info(f"   ✅ No orphan embeddings")

        logger.info(f"   Embedding shapes: {stats['embedding_shapes']}")

        is_valid = not stats["missing_embeddings"] and not stats["orphan_embeddings"]
        return is_valid, stats

    def initialize_chromadb(self) -> bool:
        """Initialize ChromaDB and load embeddings."""
        try:
            import chromadb
            from chromadb.config import Settings

            logger.info("Initializing ChromaDB...")

            # Create ChromaDB client
            self.chroma_db_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(self.chroma_db_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )

            # Get or create collection
            collection = client.get_or_create_collection(
                name="contestants_faces",
                metadata={
                    "description": "Face embeddings for contestants",
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:search_ef": 100,
                    "hnsw:M": 16,
                },
            )

            # Add embeddings to collection
            embeddings_list = []
            ids_list = []
            metadatas_list = []

            for contestant_id in sorted(self.embeddings.keys()):
                embedding = self.embeddings[contestant_id]
                embeddings_list.append(embedding.tolist())
                ids_list.append(f"contestant_{contestant_id}")

                if contestant_id in self.contestants:
                    metadata = self.contestants[contestant_id].copy()
                    metadata["contestant_id"] = str(contestant_id)
                    metadatas_list.append(metadata)
                else:
                    metadatas_list.append({"contestant_id": str(contestant_id)})

            # Batch add to ChromaDB
            collection.add(
                ids=ids_list,
                embeddings=embeddings_list,
                metadatas=metadatas_list,
            )

            logger.info(f"✅ Initialized ChromaDB with {len(embeddings_list)} embeddings")
            return True
        except ImportError:
            logger.error("ChromaDB not installed. Install with: pip install chromadb")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to initialize ChromaDB: {e}")
            return False

    def sync_with_huggingface(self) -> bool:
        """Sync contestant data with HuggingFace XET."""
        try:
            from src.integrations.huggingface_xet import HuggingFaceDataset

            hf_token = os.getenv("HF_TOKEN")
            if not hf_token:
                logger.warning(
                    "⚠️  HF_TOKEN not set. Skipping HuggingFace sync. "
                    "Set HF_TOKEN environment variable to enable."
                )
                return False

            logger.info("Syncing with HuggingFace XET...")
            dataset = HuggingFaceDataset("yellowcandle/mv-face-recognition-data", token=hf_token)

            # Upload contestant data
            dataset.upload_contestant_data()

            # Upload embeddings
            dataset.upload_embeddings()

            logger.info("✅ Successfully synced with HuggingFace XET")
            return True
        except ImportError:
            logger.warning("HuggingFace integration not available")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to sync with HuggingFace: {e}")
            return False

    def generate_report(self) -> str:
        """Generate initialization report."""
        report = [
            "\n" + "=" * 60,
            "DATABASE INITIALIZATION REPORT",
            "=" * 60,
            f"\n📁 Paths:",
            f"   Contestant CSV: {self.contestant_csv}",
            f"   Photos directory: {self.contestant_photos_dir}",
            f"   ChromaDB path: {self.chroma_db_path}",
            f"\n👥 Contestants:",
            f"   Total loaded: {len(self.contestants)}",
            f"\n🎭 Face Embeddings:",
            f"   Total loaded: {len(self.embeddings)}",
        ]

        # Check consistency
        is_valid, stats = self.verify_data_consistency()

        if is_valid:
            report.append(f"\n✅ Data consistency: VALID")
        else:
            report.append(f"\n⚠️  Data consistency: ISSUES FOUND")
            if stats["missing_embeddings"]:
                report.append(
                    f"   Missing: {len(stats['missing_embeddings'])} contestants"
                )
            if stats["orphan_embeddings"]:
                report.append(
                    f"   Orphan: {len(stats['orphan_embeddings'])} embeddings"
                )

        report.append(f"\n{'=' * 60}\n")
        return "\n".join(report)

    def run(
        self, verify_only: bool = False, sync_hf: bool = False
    ) -> bool:
        """Run complete initialization."""
        logger.info("Starting database initialization...")

        # Step 1: Load contestant CSV
        if not self.load_contestant_csv():
            return False

        # Step 2: Load embeddings
        if not self.load_embeddings_from_photos():
            return False

        # Step 3: Verify consistency
        is_valid, stats = self.verify_data_consistency()

        if verify_only:
            logger.info("Verification mode - skipping ChromaDB initialization")
            print(self.generate_report())
            return is_valid

        # Step 4: Initialize ChromaDB
        if not self.initialize_chromadb():
            return False

        # Step 5: Optional HuggingFace sync
        if sync_hf:
            self.sync_with_huggingface()

        # Print report
        print(self.generate_report())

        if is_valid:
            logger.info("✅ Database initialization completed successfully")
            return True
        else:
            logger.warning("⚠️  Database initialization completed with issues")
            return True  # Still return True as ChromaDB was initialized


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize MV Face Recognition database"
    )
    parser.add_argument(
        "--contestant-csv",
        default="metadata/contestant_info.csv",
        help="Path to contestant CSV file",
    )
    parser.add_argument(
        "--photos-dir",
        default="source/photo/contestants",
        help="Path to contestant photos directory",
    )
    parser.add_argument(
        "--chroma-path",
        default=".chroma_db",
        help="Path to ChromaDB storage",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify data only (don't initialize ChromaDB)",
    )
    parser.add_argument(
        "--sync-hf",
        action="store_true",
        help="Sync with HuggingFace XET after initialization",
    )

    args = parser.parse_args()

    initializer = DatabaseInitializer(
        contestant_csv=args.contestant_csv,
        contestant_photos_dir=args.photos_dir,
        chroma_db_path=args.chroma_path,
    )

    success = initializer.run(verify_only=args.verify, sync_hf=args.sync_hf)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
