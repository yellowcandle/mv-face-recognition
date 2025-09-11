#!/usr/bin/env python3
"""
Deduplicate embeddings in ChromaDB database.
Removes exact duplicates and very similar embeddings.
"""

import argparse
import logging
import sys
import re
from typing import Dict, List, Tuple
import numpy as np
from collections import defaultdict

# Add src to path
sys.path.append("src")

from src.database.chroma_setup import ChromaDBManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmbeddingDeduplicator:
    """Handles deduplication of face embeddings in ChromaDB."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize deduplicator."""
        self.config_path = config_path
        self.db_manager = ChromaDBManager(config_path)
        self.similarity_threshold_exact = 0.999  # For exact duplicates
        self.similarity_threshold_similar = 0.95  # For very similar embeddings

    def _is_contestant_number(self, id_: str) -> bool:
        """Check if an ID is a contestant number format."""
        return bool(re.match(r"^contestant_\d+$", id_))

    def _choose_better_id(self, id1: str, id2: str) -> Tuple[str, str]:
        """Choose which ID to keep and which to remove based on priority rules.

        Priority order:
        1. Real names over contestant numbers
        2. If both are names or both are numbers, keep the first one

        Returns:
            Tuple of (keep_id, remove_id)
        """
        id1_is_number = self._is_contestant_number(id1)
        id2_is_number = self._is_contestant_number(id2)

        # If one is a name and one is a number, keep the name
        if id1_is_number and not id2_is_number:
            return id2, id1  # Keep id2 (name), remove id1 (number)
        elif not id1_is_number and id2_is_number:
            return id1, id2  # Keep id1 (name), remove id2 (number)
        else:
            # Both are names or both are numbers - keep first occurrence
            return id1, id2

    def analyze_database(self) -> Dict:
        """Analyze the database for duplicates."""
        logger.info("🔍 Analyzing database for duplicates...")

        # Get all embeddings from the database
        try:
            collection = self.db_manager.collection
            all_data = collection.get(include=["embeddings", "metadatas"])

            if not all_data["ids"]:
                logger.warning("Database is empty")
                return {
                    "total_embeddings": 0,
                    "exact_duplicates": [],
                    "similar_duplicates": [],
                    "duplicate_ids": [],
                }

            ids = all_data["ids"]
            embeddings = all_data["embeddings"]
            all_data["metadatas"]

            logger.info(f"Found {len(ids)} embeddings in database")

            # Convert embeddings to numpy arrays for analysis
            embeddings_np = [np.array(emb) for emb in embeddings]

            # Find exact duplicates
            exact_duplicates = self._find_exact_duplicates(ids, embeddings_np)

            # Find very similar embeddings
            similar_duplicates = self._find_similar_duplicates(ids, embeddings_np)

            # Find duplicate IDs
            duplicate_ids = self._find_duplicate_ids(ids)

            analysis = {
                "total_embeddings": len(ids),
                "exact_duplicates": exact_duplicates,
                "similar_duplicates": similar_duplicates,
                "duplicate_ids": duplicate_ids,
                "unique_embeddings": len(ids)
                - len(exact_duplicates)
                - len(similar_duplicates),
            }

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing database: {e}")
            return {}

    def _find_exact_duplicates(
        self, ids: List[str], embeddings: List[np.ndarray]
    ) -> List[Tuple[str, str, float]]:
        """Find exact duplicate embeddings."""
        logger.info("Looking for exact duplicates...")
        exact_duplicates = []

        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                # Calculate cosine similarity
                similarity = np.dot(embeddings[i], embeddings[j]) / (
                    np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                )

                if similarity >= self.similarity_threshold_exact:
                    exact_duplicates.append((ids[i], ids[j], similarity))
                    logger.debug(
                        f"Exact duplicate found: {ids[i]} ↔ {ids[j]} (similarity: {similarity:.6f})"
                    )

        logger.info(f"Found {len(exact_duplicates)} exact duplicate pairs")
        return exact_duplicates

    def _find_similar_duplicates(
        self, ids: List[str], embeddings: List[np.ndarray]
    ) -> List[Tuple[str, str, float]]:
        """Find very similar embeddings (likely same person)."""
        logger.info("Looking for very similar embeddings...")
        similar_duplicates = []

        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                # Calculate cosine similarity
                similarity = np.dot(embeddings[i], embeddings[j]) / (
                    np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                )

                if (
                    self.similarity_threshold_similar
                    <= similarity
                    < self.similarity_threshold_exact
                ):
                    similar_duplicates.append((ids[i], ids[j], similarity))
                    logger.debug(
                        f"Similar embedding found: {ids[i]} ↔ {ids[j]} (similarity: {similarity:.6f})"
                    )

        logger.info(f"Found {len(similar_duplicates)} similar embedding pairs")
        return similar_duplicates

    def _find_duplicate_ids(self, ids: List[str]) -> List[str]:
        """Find duplicate IDs."""
        logger.info("Looking for duplicate IDs...")
        id_counts = defaultdict(int)

        for id_ in ids:
            id_counts[id_] += 1

        duplicate_ids = [id_ for id_, count in id_counts.items() if count > 1]
        logger.info(f"Found {len(duplicate_ids)} duplicate IDs")

        return duplicate_ids

    def remove_duplicates(self, analysis: Dict, mode: str = "exact") -> int:
        """Remove duplicates from the database using smart prioritization."""
        logger.info(
            f"🗑️ Removing duplicates in mode: {mode} (prioritizing names over numbers)"
        )

        ids_to_remove = set()
        kept_ids = set()

        if mode in ["exact", "all"]:
            # Remove exact duplicates with smart prioritization
            for id1, id2, similarity in analysis["exact_duplicates"]:
                keep_id, remove_id = self._choose_better_id(id1, id2)

                # Skip if we've already processed this pair
                if keep_id in ids_to_remove or remove_id in ids_to_remove:
                    continue

                ids_to_remove.add(remove_id)
                kept_ids.add(keep_id)

                reason = ""
                if self._is_contestant_number(
                    remove_id
                ) and not self._is_contestant_number(keep_id):
                    reason = " (prioritized name over number)"
                elif not self._is_contestant_number(
                    remove_id
                ) and self._is_contestant_number(keep_id):
                    reason = " (prioritized name over number)"
                else:
                    reason = " (kept first occurrence)"

                logger.info(
                    f"Marking {remove_id} for removal, keeping {keep_id}{reason}"
                )

        if mode in ["similar", "all"]:
            # Remove similar duplicates with smart prioritization
            for id1, id2, similarity in analysis["similar_duplicates"]:
                keep_id, remove_id = self._choose_better_id(id1, id2)

                # Skip if we've already processed this pair
                if keep_id in ids_to_remove or remove_id in ids_to_remove:
                    continue

                ids_to_remove.add(remove_id)
                kept_ids.add(keep_id)

                reason = ""
                if self._is_contestant_number(
                    remove_id
                ) and not self._is_contestant_number(keep_id):
                    reason = " (prioritized name over number)"
                elif not self._is_contestant_number(
                    remove_id
                ) and self._is_contestant_number(keep_id):
                    reason = " (prioritized name over number)"
                else:
                    reason = " (kept first occurrence)"

                logger.info(
                    f"Marking {remove_id} for removal, keeping {keep_id}{reason} (similarity: {similarity:.4f})"
                )

        # Remove duplicate IDs (keep first occurrence)
        if analysis["duplicate_ids"]:
            collection = self.db_manager.collection
            all_data = collection.get(include=["embeddings", "metadatas"])

            for duplicate_id in analysis["duplicate_ids"]:
                # Find all occurrences of this ID
                occurrences = [
                    i for i, id_ in enumerate(all_data["ids"]) if id_ == duplicate_id
                ]
                # Mark all but the first for removal
                for i in occurrences[1:]:
                    ids_to_remove.add(all_data["ids"][i])
                    logger.info(
                        f"Marking duplicate occurrence of {duplicate_id} for removal"
                    )

        # Remove the identified duplicates
        if ids_to_remove:
            try:
                collection = self.db_manager.collection
                collection.delete(ids=list(ids_to_remove))
                logger.info(
                    f"Successfully removed {len(ids_to_remove)} duplicate embeddings"
                )

                # Log summary of what was kept
                names_kept = [
                    id_ for id_ in kept_ids if not self._is_contestant_number(id_)
                ]
                numbers_kept = [
                    id_ for id_ in kept_ids if self._is_contestant_number(id_)
                ]
                logger.info(
                    f"Summary: Kept {len(names_kept)} names and {len(numbers_kept)} contestant numbers"
                )

                return len(ids_to_remove)
            except Exception as e:
                logger.error(f"Error removing duplicates: {e}")
                return 0
        else:
            logger.info("No duplicates to remove")
            return 0

    def standardize_to_names(self) -> Dict:
        """Attempt to standardize all IDs to real names by examining patterns."""
        logger.info("🔄 Analyzing database for name standardization opportunities...")

        collection = self.db_manager.collection
        all_data = collection.get(include=["embeddings", "metadatas"])

        if not all_data["ids"]:
            return {"changed": 0, "total": 0}

        ids = all_data["ids"]
        name_count = len([id_ for id_ in ids if not self._is_contestant_number(id_)])
        number_count = len([id_ for id_ in ids if self._is_contestant_number(id_)])

        logger.info(
            f"Current database state: {name_count} names, {number_count} contestant numbers"
        )

        return {
            "total": len(ids),
            "names": name_count,
            "numbers": number_count,
            "consistency": "Good"
            if number_count == 0
            else "Mixed"
            if name_count > number_count
            else "Poor",
        }

    def optimize_database(self):
        """Optimize the database after deduplication."""
        logger.info("🔧 Optimizing database...")

        # ChromaDB doesn't have explicit optimization, but we can rebuild the collection
        # Get all remaining data
        collection = self.db_manager.collection
        all_data = collection.get(include=["embeddings", "metadatas"])

        if not all_data["ids"]:
            logger.info("Database is empty after deduplication")
            return

        # Recreate the collection
        self.db_manager.client.delete_collection("contestants_faces")
        self.db_manager.collection = self.db_manager.client.create_collection(
            name="contestants_faces",
            metadata={"description": "Face embeddings for contestants"},
        )

        # Re-add all data
        self.db_manager.collection.add(
            embeddings=all_data["embeddings"],
            metadatas=all_data["metadatas"],
            ids=all_data["ids"],
        )

        logger.info("Database optimization completed")

    def print_analysis_report(self, analysis: Dict):
        """Print a detailed analysis report."""
        print("\n" + "=" * 60)
        print("📊 EMBEDDING DEDUPLICATION ANALYSIS")
        print("=" * 60)

        print("\n🔢 Database Overview:")
        print(f"  Total embeddings: {analysis['total_embeddings']}")
        print(f"  Unique embeddings: {analysis['unique_embeddings']}")

        print("\n🔍 Duplicates Found:")
        print(f"  Exact duplicates: {len(analysis['exact_duplicates'])} pairs")
        print(f"  Similar duplicates: {len(analysis['similar_duplicates'])} pairs")
        print(f"  Duplicate IDs: {len(analysis['duplicate_ids'])} IDs")

        if analysis["exact_duplicates"]:
            print(
                f"\n📋 Exact Duplicates (similarity >= {self.similarity_threshold_exact}):"
            )
            print("     [Will prioritize names over contestant numbers]")
            for i, (id1, id2, similarity) in enumerate(
                analysis["exact_duplicates"][:10]
            ):
                keep_id, remove_id = self._choose_better_id(id1, id2)
                priority_reason = ""
                if self._is_contestant_number(
                    remove_id
                ) and not self._is_contestant_number(keep_id):
                    priority_reason = " → Keep name"
                elif not self._is_contestant_number(
                    remove_id
                ) and self._is_contestant_number(keep_id):
                    priority_reason = " → Keep name"

                print(
                    f"  {i+1:2d}. {id1} ↔ {id2} (similarity: {similarity:.6f}){priority_reason}"
                )
                print(f"      Will keep: {keep_id}, remove: {remove_id}")
            if len(analysis["exact_duplicates"]) > 10:
                print(f"  ... and {len(analysis['exact_duplicates']) - 10} more")

        if analysis["similar_duplicates"]:
            print(
                f"\n📋 Similar Duplicates (similarity >= {self.similarity_threshold_similar}):"
            )
            print("     [Will prioritize names over contestant numbers]")
            for i, (id1, id2, similarity) in enumerate(
                analysis["similar_duplicates"][:10]
            ):
                keep_id, remove_id = self._choose_better_id(id1, id2)
                priority_reason = ""
                if self._is_contestant_number(
                    remove_id
                ) and not self._is_contestant_number(keep_id):
                    priority_reason = " → Keep name"
                elif not self._is_contestant_number(
                    remove_id
                ) and self._is_contestant_number(keep_id):
                    priority_reason = " → Keep name"

                print(
                    f"  {i+1:2d}. {id1} ↔ {id2} (similarity: {similarity:.6f}){priority_reason}"
                )
                print(f"      Will keep: {keep_id}, remove: {remove_id}")
            if len(analysis["similar_duplicates"]) > 10:
                print(f"  ... and {len(analysis['similar_duplicates']) - 10} more")

        if analysis["duplicate_ids"]:
            print("\n📋 Duplicate IDs:")
            for i, duplicate_id in enumerate(analysis["duplicate_ids"][:10]):
                print(f"  {i+1:2d}. {duplicate_id}")
            if len(analysis["duplicate_ids"]) > 10:
                print(f"  ... and {len(analysis['duplicate_ids']) - 10} more")

        # Calculate potential savings
        total_duplicates = len(analysis["exact_duplicates"]) + len(
            analysis["similar_duplicates"]
        )
        if total_duplicates > 0:
            savings_percent = (total_duplicates / analysis["total_embeddings"]) * 100
            print("\n💾 Potential Savings:")
            print(f"  Embeddings to remove: {total_duplicates}")
            print(f"  Storage reduction: {savings_percent:.1f}%")

        print("=" * 60)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Deduplicate embeddings in ChromaDB")
    parser.add_argument(
        "--analyze", action="store_true", help="Analyze database for duplicates"
    )
    parser.add_argument(
        "--remove",
        choices=["exact", "similar", "all"],
        help="Remove duplicates: exact, similar, or all",
    )
    parser.add_argument(
        "--optimize", action="store_true", help="Optimize database after deduplication"
    )
    parser.add_argument(
        "--standardize", action="store_true", help="Show database standardization info"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without actually removing",
    )
    parser.add_argument(
        "--exact-threshold",
        type=float,
        default=0.999,
        help="Similarity threshold for exact duplicates (default: 0.999)",
    )
    parser.add_argument(
        "--similar-threshold",
        type=float,
        default=0.95,
        help="Similarity threshold for similar duplicates (default: 0.95)",
    )

    args = parser.parse_args()

    # If no arguments, run analysis
    if not any([args.analyze, args.remove, args.optimize, args.standardize]):
        args.analyze = True

    print("🔧 MV Face Recognition - Smart Embedding Deduplication")
    print("=" * 50)

    # Initialize deduplicator
    deduplicator = EmbeddingDeduplicator()

    # Set custom thresholds if provided
    if args.exact_threshold:
        deduplicator.similarity_threshold_exact = args.exact_threshold
    if args.similar_threshold:
        deduplicator.similarity_threshold_similar = args.similar_threshold

    # Show standardization info if requested
    if args.standardize:
        std_info = deduplicator.standardize_to_names()
        print("\n📊 Database Standardization Status:")
        print(f"  Total embeddings: {std_info['total']}")
        print(f"  Real names: {std_info['names']}")
        print(f"  Contestant numbers: {std_info['numbers']}")
        print(f"  Consistency: {std_info['consistency']}")
        return True

    # Analyze database
    analysis = deduplicator.analyze_database()

    if not analysis:
        logger.error("Failed to analyze database")
        return False

    # Print analysis report
    deduplicator.print_analysis_report(analysis)

    # Remove duplicates if requested
    if args.remove and not args.dry_run:
        removed_count = deduplicator.remove_duplicates(analysis, args.remove)
        print(f"\n✅ Removed {removed_count} duplicate embeddings")

        # Re-analyze to show new state
        new_analysis = deduplicator.analyze_database()
        print("\n📊 After deduplication:")
        print(f"  Total embeddings: {new_analysis['total_embeddings']}")
        print(f"  Exact duplicates: {len(new_analysis['exact_duplicates'])}")
        print(f"  Similar duplicates: {len(new_analysis['similar_duplicates'])}")

        # Show standardization status
        std_info = deduplicator.standardize_to_names()
        print("\n📊 Database Consistency:")
        print(f"  Real names: {std_info['names']}")
        print(f"  Contestant numbers: {std_info['numbers']}")
        print(f"  Status: {std_info['consistency']}")

    elif args.remove and args.dry_run:
        # Show what would be removed with smart prioritization
        ids_to_remove = set()
        kept_ids = set()

        if args.remove in ["exact", "all"]:
            for id1, id2, similarity in analysis["exact_duplicates"]:
                keep_id, remove_id = deduplicator._choose_better_id(id1, id2)
                ids_to_remove.add(remove_id)
                kept_ids.add(keep_id)

        if args.remove in ["similar", "all"]:
            for id1, id2, similarity in analysis["similar_duplicates"]:
                keep_id, remove_id = deduplicator._choose_better_id(id1, id2)
                ids_to_remove.add(remove_id)
                kept_ids.add(keep_id)

        print(f"\n🔍 DRY RUN - Would remove {len(ids_to_remove)} embeddings:")
        names_to_remove = [
            id_ for id_ in ids_to_remove if not deduplicator._is_contestant_number(id_)
        ]
        numbers_to_remove = [
            id_ for id_ in ids_to_remove if deduplicator._is_contestant_number(id_)
        ]

        print(f"  Names to remove: {len(names_to_remove)}")
        print(f"  Numbers to remove: {len(numbers_to_remove)}")

        for i, id_to_remove in enumerate(list(ids_to_remove)[:10]):
            print(f"  {i+1:2d}. {id_to_remove}")
        if len(ids_to_remove) > 10:
            print(f"  ... and {len(ids_to_remove) - 10} more")

    # Optimize database if requested
    if args.optimize and not args.dry_run:
        deduplicator.optimize_database()
        print("\n🔧 Database optimization completed")

    print("\n✅ Deduplication process completed!")
    return True


if __name__ == "__main__":
    main()
