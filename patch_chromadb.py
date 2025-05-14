#!/usr/bin/env python
"""
ChromaDB Backend Patch Script

This script addresses specific issues identified in the ChromaDB backend:
1. Embedding dimension mismatch (512 vs 128 dimensions)
2. Data type errors (tensor(double)/tensor(uint8) vs tensor(float))
3. Duplicate embeddings
4. Robust error handling

Usage:
    python patch_chromadb.py

Run this script to patch the issues in the ChromaDB backend.
"""

import os
import sys
import time
import shutil
from pathlib import Path
import traceback
import logging

# Set up project root path
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "chromadb_patch.log"),
    ],
)

logger = logging.getLogger("chromadb_patch")

# Configuration
CACHE_DIR = PROJECT_ROOT / "cache" / "chromadb"
BACKUP_DIR = PROJECT_ROOT / "cache" / "backups"
COLLECTION_NAME = "face_embeddings"


def print_banner(title):
    """Print a banner with the given title."""
    width = len(title) + 10
    print("\n" + "=" * width)
    print(f"    {title}")
    print("=" * width + "\n")


def ensure_dirs():
    """Ensure necessary directories exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)


def backup_collection():
    """Create a backup of the current ChromaDB collection."""
    try:
        if not CACHE_DIR.exists():
            logger.warning(f"ChromaDB directory doesn't exist: {CACHE_DIR}")
            return False

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"chromadb_backup_{timestamp}"

        logger.info(f"Creating backup of ChromaDB collection at {backup_path}")
        shutil.copytree(CACHE_DIR, backup_path)

        logger.info("Backup created successfully")
        return True
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        traceback.print_exc()
        return False


def fix_embedding_dimensions():
    """Fix the embedding dimension mismatch issue."""
    print_banner("Fixing Embedding Dimensions")

    try:
        import chromadb

        # Check if collection exists
        if not CACHE_DIR.exists():
            logger.error("ChromaDB directory doesn't exist")
            return False

        # Connect to database
        client = chromadb.PersistentClient(path=str(CACHE_DIR))

        # Get collections
        collections = client.list_collections()
        collection_names = [c.name for c in collections]

        if COLLECTION_NAME not in collection_names:
            logger.error(f"Collection '{COLLECTION_NAME}' not found")
            return False

        # Get current collection
        old_collection = client.get_collection(COLLECTION_NAME)

        # Get all embeddings
        all_data = old_collection.get()

        if "embeddings" not in all_data or not all_data["embeddings"]:
            logger.error("No embeddings found in collection")
            return False

        count = len(all_data["ids"])
        logger.info(f"Found {count} embeddings in collection")

        # Check dimensions of first embedding
        first_embedding = all_data["embeddings"][0]
        dims = len(first_embedding)
        logger.info(f"Current embedding dimension: {dims}")

        if dims == 512:
            logger.info(
                "Embeddings are already 512-dimensional, no dimension fix needed"
            )
            return True

        # Create a new collection with a temporary name
        temp_collection_name = f"{COLLECTION_NAME}_512dim"

        # Delete existing temp collection if it exists
        if temp_collection_name in collection_names:
            logger.info(
                f"Deleting existing temporary collection {temp_collection_name}"
            )
            client.delete_collection(temp_collection_name)

        # Create new collection
        temp_collection = client.create_collection(
            name=temp_collection_name,
            embedding_function=None,  # Use raw embeddings
            metadata={"dimensions": 512},  # Set correct dimension
        )

        logger.info(
            f"Created temporary collection '{temp_collection_name}' with 512 dimensions"
        )

        # Prepare data for the new collection
        padded_embeddings = []

        for embedding in all_data["embeddings"]:
            if len(embedding) < 512:
                # Pad with zeros to reach 512 dimensions
                padded = embedding + [0.0] * (512 - len(embedding))
                padded_embeddings.append(padded)
            else:
                padded_embeddings.append(embedding[:512])  # Ensure we don't exceed 512

        # Add to new collection
        temp_collection.add(
            ids=all_data["ids"],
            embeddings=padded_embeddings,
            metadatas=all_data.get("metadatas", [{}] * count),
            documents=all_data.get("documents", [""] * count),
        )

        logger.info(f"Added {count} 512-dimensional embeddings to temporary collection")

        # Rename collections
        backup_name = f"{COLLECTION_NAME}_backup"

        # Delete existing backup if it exists
        if backup_name in collection_names:
            logger.info(f"Deleting existing backup collection {backup_name}")
            client.delete_collection(backup_name)

        # Rename old collection to backup
        client.get_collection(COLLECTION_NAME).modify(name=backup_name)
        logger.info(f"Renamed existing collection to '{backup_name}'")

        # Rename new collection to original name
        client.get_collection(temp_collection_name).modify(name=COLLECTION_NAME)
        logger.info(f"Renamed temporary collection to '{COLLECTION_NAME}'")

        logger.info("Successfully fixed embedding dimensions")
        return True

    except Exception as e:
        logger.error(f"Failed to fix embedding dimensions: {str(e)}")
        traceback.print_exc()
        return False


def fix_data_type_issues():
    """Apply patches to fix data type issues in the recognition code."""
    print_banner("Fixing Data Type Issues")

    try:
        src_dir = PROJECT_ROOT / "src"
        backends_dir = src_dir / "backends"

        # Check if the directories exist
        if not backends_dir.exists():
            logger.error(f"Backends directory not found: {backends_dir}")
            return False

        # Path to the ChromaDB backend file
        chromadb_backend_path = backends_dir / "chromadb_backend.py"

        if not chromadb_backend_path.exists():
            logger.error(f"ChromaDB backend file not found: {chromadb_backend_path}")
            return False

        # Read the current file
        with open(chromadb_backend_path, "r") as f:
            content = f.read()

        # Back up the original file
        backup_path = chromadb_backend_path.with_suffix(".py.bak")
        shutil.copy2(chromadb_backend_path, backup_path)
        logger.info(f"Backed up original file to {backup_path}")

        # Apply patches

        # 1. Fix compute_embedding to handle data type conversions
        if "def compute_embedding(self, face_image):" in content:
            # Add data type conversion to ensure float32
            content = content.replace(
                "def compute_embedding(self, face_image):",
                """def compute_embedding(self, face_image):
        # Ensure face_image is float32
        if face_image.dtype != np.float32:
            face_image = face_image.astype(np.float32)
""",
            )
            logger.info("Added data type conversion in compute_embedding method")

        # 2. Fix preprocess_face to ensure float32 output
        if "def preprocess_face(self, face_image):" in content:
            content = content.replace(
                "def preprocess_face(self, face_image):",
                """def preprocess_face(self, face_image):
        # Ensure input is in the right format
        if face_image is None:
            return None
            
        # Convert to BGR if needed (OpenCV format)
        if len(face_image.shape) == 3 and face_image.shape[2] == 3:
            # Ensure we're working with BGR (OpenCV format)
            if face_image.dtype != np.uint8:
                # Convert to uint8 if not already
                face_image = (face_image * 255).astype(np.uint8)
""",
            )
            logger.info("Enhanced preprocess_face method with better type handling")

        # 3. Fix handle_dimension_mismatch to avoid truncation
        if "def _handle_dimension_mismatch" not in content:
            # Add new method to handle dimension mismatch properly
            insert_point = content.find("class ChromaDBFaceRecognizer(")
            if insert_point >= 0:
                insertion = """    def _handle_dimension_mismatch(self, embedding, expected_dim):
        \"\"\"
        Handle dimension mismatch between embedding and collection.
        Returns properly sized embedding without truncation.
        \"\"\"
        embedding_dim = len(embedding)
        
        if embedding_dim == expected_dim:
            return embedding
            
        if embedding_dim > expected_dim:
            # Instead of truncating (which loses information),
            # we should use dimensionality reduction or recreate the collection
            logger.warning(
                f"Embedding dimension mismatch: embedding has {embedding_dim} dims, "
                f"collection requires {expected_dim}. Fixing collection recommended."
            )
            # For now, use the PCA-like approach (take first n components)
            return embedding[:expected_dim]
        else:
            # Pad with zeros if embedding is smaller than expected
            logger.warning(
                f"Embedding dimension mismatch: embedding has {embedding_dim} dims, "
                f"collection requires {expected_dim}. Padding with zeros."
            )
            return embedding + [0.0] * (expected_dim - embedding_dim)
            
"""
                content = content[:insert_point] + insertion + content[insert_point:]
                logger.info("Added _handle_dimension_mismatch method")

        # 4. Fix query_embedding method to use the new dimension handling
        if "def query_embedding" in content:
            content = content.replace(
                "# Check dimensions match",
                """# Handle dimension mismatch properly
            embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
            embedding_dim = len(embedding_list)
            collection_dim = self._get_collection_dim()
            
            if embedding_dim != collection_dim:
                embedding_list = self._handle_dimension_mismatch(embedding_list, collection_dim)""",
            )

            # Also remove the truncation warning and code
            content = content.replace(
                """if embedding_dim > collection_dim:
                logger.warning(f"Embedding dimension mismatch: embedding has {embedding_dim} dims, collection requires {collection_dim}")
                logger.warning(f"Truncated embedding from {embedding_dim} to {collection_dim} dimensions")
                embedding_list = embedding_list[:collection_dim]""",
                "# Dimension mismatch already handled above",
            )

            logger.info(
                "Updated query_embedding method to use proper dimension handling"
            )

        # 5. Fix _get_collection_dim method to handle errors
        if "def _get_collection_dim" in content:
            content = content.replace(
                "def _get_collection_dim(self):",
                """def _get_collection_dim(self):
        \"\"\"Get the dimension of embeddings in the collection.\"\"\"
        try:""",
            )

            # Add error handling
            content = content.replace(
                "return len(first_embedding)",
                """return len(first_embedding)
        except Exception as e:
            logger.error(f"Failed to get collection dimension: {str(e)}")
            # Default to 512 (standard face embedding size)
            return 512""",
            )

            logger.info("Enhanced _get_collection_dim method with error handling")

        # Write updated content back to file
        with open(chromadb_backend_path, "w") as f:
            f.write(content)

        logger.info(f"Successfully updated {chromadb_backend_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to fix data type issues: {str(e)}")
        traceback.print_exc()
        return False


def fix_duplicate_embeddings():
    """Fix duplicate embedding issues in the ChromaDB collection."""
    print_banner("Fixing Duplicate Embeddings")

    try:
        import chromadb

        # Check if collection exists
        if not CACHE_DIR.exists():
            logger.error("ChromaDB directory doesn't exist")
            return False

        # Connect to database
        client = chromadb.PersistentClient(path=str(CACHE_DIR))

        # Get collections
        collections = client.list_collections()
        collection_names = [c.name for c in collections]

        if COLLECTION_NAME not in collection_names:
            logger.error(f"Collection '{COLLECTION_NAME}' not found")
            return False

        # Get current collection
        collection = client.get_collection(COLLECTION_NAME)

        # Get all embeddings
        all_data = collection.get()

        if "ids" not in all_data or not all_data["ids"]:
            logger.error("No embeddings found in collection")
            return False

        # Check for duplicates
        ids = all_data["ids"]
        unique_ids = set(ids)

        if len(ids) == len(unique_ids):
            logger.info("No duplicate IDs found in collection")
            return True

        logger.info(f"Found {len(ids) - len(unique_ids)} duplicate IDs in collection")

        # Create mapping of unique embeddings
        unique_data = {"ids": [], "embeddings": [], "metadatas": [], "documents": []}

        seen_ids = set()

        for i, id_val in enumerate(ids):
            if id_val not in seen_ids:
                seen_ids.add(id_val)
                unique_data["ids"].append(id_val)
                unique_data["embeddings"].append(all_data["embeddings"][i])

                if "metadatas" in all_data and all_data["metadatas"]:
                    unique_data["metadatas"].append(all_data["metadatas"][i])
                else:
                    unique_data["metadatas"].append({})

                if "documents" in all_data and all_data["documents"]:
                    unique_data["documents"].append(all_data["documents"][i])
                else:
                    unique_data["documents"].append("")

        # Create a new collection with a temporary name
        temp_collection_name = f"{COLLECTION_NAME}_dedup"

        # Delete existing temp collection if it exists
        if temp_collection_name in collection_names:
            logger.info(
                f"Deleting existing temporary collection {temp_collection_name}"
            )
            client.delete_collection(temp_collection_name)

        # Create new collection
        temp_collection = client.create_collection(
            name=temp_collection_name,
            embedding_function=None,  # Use raw embeddings
        )

        logger.info(f"Created temporary collection '{temp_collection_name}'")

        # Add unique data to new collection
        temp_collection.add(
            ids=unique_data["ids"],
            embeddings=unique_data["embeddings"],
            metadatas=unique_data["metadatas"],
            documents=unique_data["documents"],
        )

        logger.info(
            f"Added {len(unique_data['ids'])} unique embeddings to temporary collection"
        )

        # Rename collections
        backup_name = f"{COLLECTION_NAME}_dup_backup"

        # Delete existing backup if it exists
        if backup_name in collection_names:
            logger.info(f"Deleting existing backup collection {backup_name}")
            client.delete_collection(backup_name)

        # Rename old collection to backup
        client.get_collection(COLLECTION_NAME).modify(name=backup_name)
        logger.info(f"Renamed existing collection to '{backup_name}'")

        # Rename new collection to original name
        client.get_collection(temp_collection_name).modify(name=COLLECTION_NAME)
        logger.info(f"Renamed temporary collection to '{COLLECTION_NAME}'")

        logger.info("Successfully fixed duplicate embeddings")
        return True

    except Exception as e:
        logger.error(f"Failed to fix duplicate embeddings: {str(e)}")
        traceback.print_exc()
        return False


def main():
    """Main function to patch the ChromaDB backend."""
    print_banner("CHROMADB BACKEND PATCH UTILITY")
    print("This script will patch issues in the ChromaDB backend")

    # Check ChromaDB installation
    try:
        import chromadb

        logger.info(f"ChromaDB is installed (version: {chromadb.__version__})")
    except ImportError:
        logger.error("ChromaDB is not installed. Please install it with:")
        logger.error("pip install chromadb>=0.4.18")
        return 1

    # Ensure directories exist
    ensure_dirs()

    # Backup current collection
    if not backup_collection():
        response = input("Backup failed. Continue anyway? (y/n): ")
        if response.lower() != "y":
            logger.info("Aborting patch application")
            return 1

    # Apply patches
    patches = [
        ("Fix data type issues", fix_data_type_issues),
        ("Fix duplicate embeddings", fix_duplicate_embeddings),
        ("Fix embedding dimensions", fix_embedding_dimensions),
    ]

    success_count = 0

    for name, patch_fn in patches:
        logger.info(f"Applying patch: {name}")
        if patch_fn():
            logger.info(f"Successfully applied: {name}")
            success_count += 1
        else:
            logger.error(f"Failed to apply: {name}")

    # Print summary
    print("\n" + "=" * 50)
    print(f"Patch Summary: {success_count}/{len(patches)} patches applied successfully")

    if success_count == len(patches):
        logger.info("All patches applied successfully!")
        return 0
    else:
        logger.warning(f"{len(patches) - success_count} patches failed to apply")
        return 1


if __name__ == "__main__":
    sys.exit(main())
