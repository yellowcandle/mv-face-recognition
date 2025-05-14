#!/usr/bin/env python
"""
ChromaDB Backend Compatibility Fix

This script addresses compatibility issues with ChromaDB v0.6.2 and fixes data type errors.
It provides a streamlined approach to fix the most critical issues in the face recognition system.

Usage:
    python fix_syntax.py
"""

import sys
import shutil
from pathlib import Path
import logging

# Set up project root path
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("chromadb_fix")

# Configuration
CACHE_DIR = PROJECT_ROOT / "cache" / "chromadb"
BACKENDS_DIR = PROJECT_ROOT / "src" / "backends"


def print_section(title):
    """Print a section header."""
    width = 60
    print("\n" + "=" * width)
    print(f"{title.center(width)}")
    print("=" * width + "\n")


def backup_file(file_path):
    """Create a backup of a file."""
    backup_path = file_path.with_suffix(f"{file_path.suffix}.bak")
    shutil.copy2(file_path, backup_path)
    logger.info(f"Backed up file to {backup_path}")
    return backup_path


def check_chromadb_version():
    """Check the installed ChromaDB version."""
    try:
        import chromadb

        version = chromadb.__version__
        logger.info(f"ChromaDB version: {version}")
        return version
    except ImportError:
        logger.error("ChromaDB is not installed")
        return None


def fix_data_type_issues():
    """Apply patches to fix data type issues in the recognition code."""
    print_section("Fixing Data Type Issues")

    try:
        # Path to the ChromaDB backend file
        chromadb_backend_path = BACKENDS_DIR / "chromadb_backend.py"

        if not chromadb_backend_path.exists():
            logger.error(f"ChromaDB backend file not found: {chromadb_backend_path}")
            return False

        # Read the current file
        with open(chromadb_backend_path, "r") as f:
            content = f.read()

        # Back up the original file
        backup_file(chromadb_backend_path)

        # Fix 1: Add data type conversion to ensure correct tensor types
        if "def compute_embedding(self, face_image):" in content:
            content = content.replace(
                "def compute_embedding(self, face_image):",
                """def compute_embedding(self, face_image):
        # Convert to proper data type if needed
        import numpy as np
        if face_image is not None and face_image.dtype != np.float32:
            face_image = face_image.astype(np.float32)
""",
            )
            logger.info("Added data type conversion in compute_embedding method")

        # Fix 2: Ensure proper handling of dimension mismatch
        if "# Handle dimension mismatch" not in content:
            # Look for the point where we would need to handle dimension mismatch
            query_start = content.find("def query_embedding")
            if query_start >= 0:
                # Find the end of the method signature
                method_start = content.find(":", query_start)
                if method_start >= 0:
                    # Add code after the method signature
                    insert_point = method_start + 1
                    insert_code = """
        # Convert embedding to appropriate format
        import numpy as np
        if isinstance(embedding, np.ndarray):
            embedding_list = embedding.tolist()
        else:
            embedding_list = embedding
            
        # Check dimensions and handle mismatch
        try:
            collection_dim = None
            if hasattr(self, '_collection') and self._collection:
                # Try to get dimension from existing collection
                first_result = self._collection.peek(1)
                if first_result and 'embeddings' in first_result and first_result['embeddings']:
                    collection_dim = len(first_result['embeddings'][0])
            
            if collection_dim and len(embedding_list) != collection_dim:
                logger.warning(f"Embedding dimension mismatch: {len(embedding_list)} vs {collection_dim}")
                if len(embedding_list) > collection_dim:
                    # Truncate embedding to match collection
                    embedding_list = embedding_list[:collection_dim]
                    logger.warning(f"Truncated embedding to {collection_dim} dimensions")
                else:
                    # Pad embedding with zeros
                    embedding_list = embedding_list + [0.0] * (collection_dim - len(embedding_list))
                    logger.warning(f"Padded embedding to {collection_dim} dimensions")
        except Exception as e:
            logger.warning(f"Error checking dimensions: {str(e)}")
            # Continue with original embedding
"""
                    # Insert the code after the method signature
                    content = (
                        content[:insert_point] + insert_code + content[insert_point:]
                    )
                    logger.info(
                        "Added dimension mismatch handling in query_embedding method"
                    )

        # Write updated content back to file
        with open(chromadb_backend_path, "w") as f:
            f.write(content)

        logger.info(f"Successfully updated {chromadb_backend_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to fix data type issues: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main function to fix ChromaDB issues."""
    print_section("CHROMADB FACE RECOGNITION FIX")

    # Check ChromaDB version
    version = check_chromadb_version()
    if not version:
        return 1

    # Apply fixes
    fixes = [("Fix data type issues", fix_data_type_issues)]

    success_count = 0
    for name, fix_fn in fixes:
        logger.info(f"Applying fix: {name}")
        if fix_fn():
            logger.info(f"✅ Successfully applied: {name}")
            success_count += 1
        else:
            logger.error(f"❌ Failed to apply: {name}")

    # Print summary
    print_section("Summary")
    print(f"Applied {success_count}/{len(fixes)} fixes successfully")

    if success_count == len(fixes):
        print("All fixes applied successfully! Try running the system again.")
    else:
        print(f"{len(fixes) - success_count} fixes failed to apply.")

    print("\nTo test the fix, run:")
    print("  python -m src.main --recognizer-backend chromadb --debug")

    return 0 if success_count == len(fixes) else 1


if __name__ == "__main__":
    sys.exit(main())
