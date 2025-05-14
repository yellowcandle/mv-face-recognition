#!/usr/bin/env python
"""
Comprehensive ChromaDB Backend Fix

This script fixes critical issues with the ChromaDB backend:
1. Data type conversion for ONNX model compatibility
2. Proper handling of embedding dimension mismatch
3. Full fix for the recognition system

Usage:
    python fix_chromadb.py
"""

import sys
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("chromadb_fix")

# Root paths
PROJECT_ROOT = Path(__file__).parent.absolute()
SRC_DIR = PROJECT_ROOT / "src"
BACKENDS_DIR = SRC_DIR / "backends"
CACHE_DIR = PROJECT_ROOT / "cache" / "chromadb"


def print_header(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f" {title} ".center(70, "="))
    print("=" * 70)


def backup_file(file_path):
    """Create a backup of a file."""
    if file_path.exists():
        backup_path = file_path.with_suffix(f"{file_path.suffix}.bak")
        shutil.copy2(file_path, backup_path)
        logger.info(f"Backed up {file_path} to {backup_path}")
        return True
    else:
        logger.error(f"File not found: {file_path}")
        return False


def fix_data_types():
    """Fix the data type issue in compute_embedding method."""
    print_header("Fixing Data Type Issues")

    # Path to file containing compute_embedding method
    chromadb_backend_path = BACKENDS_DIR / "chromadb_backend.py"

    if not backup_file(chromadb_backend_path):
        return False

    try:
        # Read file content
        with open(chromadb_backend_path, "r") as f:
            content = f.read()

        # Fix the compute_embedding method
        if "def compute_embedding(self, face_image):" in content:
            # Replace the method with a fixed version
            content = content.replace(
                "def compute_embedding(self, face_image):",
                """def compute_embedding(self, face_image):
        # Ensure face_image is the correct data type (float32) for ONNX
        import numpy as np
        if face_image is None:
            return None
            
        # Convert to float32 if needed
        if face_image.dtype != np.float32:
            face_image = face_image.astype(np.float32)
            
        # Ensure image is in the correct range for the model
        if face_image.max() > 1.0 and face_image.dtype == np.float32:
            face_image = face_image / 255.0
""",
            )
            logger.info("Fixed compute_embedding method with proper type conversion")

        # Fix preprocess_face method to ensure correct output type
        if "def preprocess_face(self, face_image):" in content:
            content = content.replace(
                "def preprocess_face(self, face_image):",
                """def preprocess_face(self, face_image):
        # Ensure input is in the right format
        import numpy as np
        if face_image is None:
            return None
            
        # Make a copy to avoid modifying the original
        face_image = face_image.copy()
        
        # Convert to BGR if needed (OpenCV format)
        if len(face_image.shape) == 3 and face_image.shape[2] == 3:
            # Ensure we're working with proper data type
            if face_image.dtype != np.uint8 and face_image.max() <= 1.0:
                # Convert from float [0-1] to uint8 [0-255]
                face_image = (face_image * 255).astype(np.uint8)
            elif face_image.dtype != np.uint8:
                # Convert to uint8 if not already
                face_image = face_image.astype(np.uint8)
""",
            )
            logger.info("Fixed preprocess_face method with better type handling")

        # Fix dimension mismatch issue
        dimension_handler = """
    def _handle_dimension_mismatch(self, embedding, collection_dim):
        \"\"\"
        Handle dimension mismatch between embedding and collection
        without just truncating the embedding.
        \"\"\"
        import numpy as np
        
        # Convert to numpy array if needed
        if not isinstance(embedding, np.ndarray):
            embedding = np.array(embedding)
            
        embedding_dim = embedding.shape[0]
        
        if embedding_dim == collection_dim:
            return embedding
            
        logger.warning(f"Embedding dimension mismatch: {embedding_dim} vs {collection_dim}")
        
        if embedding_dim > collection_dim:
            # Instead of simple truncation, perform dimensionality reduction
            # Use a simple method: average nearby dimensions
            ratio = embedding_dim / collection_dim
            new_embedding = np.zeros(collection_dim)
            
            for i in range(collection_dim):
                start = int(i * ratio)
                end = int((i+1) * ratio)
                # Ensure we have at least one element
                end = max(start+1, end)
                # Average the values in this range
                new_embedding[i] = np.mean(embedding[start:end])
                
            logger.warning(f"Reduced embedding from {embedding_dim} to {collection_dim} dimensions")
            return new_embedding
        else:
            # Pad with zeros if embedding is smaller than expected
            new_embedding = np.zeros(collection_dim)
            new_embedding[:embedding_dim] = embedding
            logger.warning(f"Padded embedding from {embedding_dim} to {collection_dim} dimensions")
            return new_embedding
"""

        # Add the dimension handler method
        if "_handle_dimension_mismatch" not in content:
            # Insert the method at the beginning of the class
            class_start = content.find("class ChromaDBFaceRecognizer(")
            if class_start >= 0:
                # Find the end of the class signature
                class_def_end = content.find(":", class_start)
                if class_def_end >= 0:
                    # Insert after the class declaration
                    insert_point = content.find("\n", class_def_end) + 1
                    # First, count the indentation
                    next_line_start = content.find("\n", class_def_end) + 1
                    next_line_end = content.find("\n", next_line_start)
                    first_line = content[next_line_start:next_line_end]
                    indentation = len(first_line) - len(first_line.lstrip())
                    # Add indentation to the dimension handler
                    indented_handler = "\n".join(
                        " " * indentation + line
                        for line in dimension_handler.split("\n")
                    )
                    content = (
                        content[:insert_point]
                        + indented_handler
                        + content[insert_point:]
                    )
                    logger.info("Added dimension mismatch handler method")

        # Fix query_embedding to use the dimension handler
        if "def query_embedding" in content:
            # Modify the method to use our new handler
            if "if embedding_dim > collection_dim:" in content:
                # Find the start of the dimension check
                dim_check_start = content.find("if embedding_dim > collection_dim:")
                if dim_check_start >= 0:
                    # Find the next line after the truncation code
                    truncation_end = content.find("\n", dim_check_start)
                    truncation_end = content.find("\n", truncation_end + 1)
                    truncation_end = content.find("\n", truncation_end + 1)
                    # Replace with our handler
                    replacement = "            # Use dimension handler\n            embedding_list = self._handle_dimension_mismatch(embedding_list, collection_dim)"
                    content = (
                        content[:dim_check_start]
                        + replacement
                        + content[truncation_end:]
                    )
                    logger.info("Fixed dimension handling in query_embedding method")

        # Write the updated content back to the file
        with open(chromadb_backend_path, "w") as f:
            f.write(content)

        logger.info(f"Successfully updated {chromadb_backend_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to fix data type issues: {e}")
        import traceback

        traceback.print_exc()
        return False


def fix_core_recognizer():
    """Fix the core recognizer to ensure proper data type handling."""
    print_header("Fixing Core Recognizer")

    # Path to file containing the StandardFaceRecognizer
    recognizer_path = SRC_DIR / "core" / "recognizer.py"

    if not backup_file(recognizer_path):
        return False

    try:
        # Read file content
        with open(recognizer_path, "r") as f:
            content = f.read()

        # Find and fix the compute_embedding method to handle data types
        if "def compute_embedding" in content:
            # Find the method
            method_start = content.find("def compute_embedding")
            if method_start >= 0:
                # Find where the method calls the ONNX model
                onnx_call_start = content.find("self.onnx_session.run(", method_start)
                if onnx_call_start >= 0:
                    # Find the start of the method body (after the signature)
                    method_body_start = content.find(":", method_start)
                    method_body_start = content.find("\n", method_body_start) + 1

                    # Determine indentation
                    next_line_end = content.find("\n", method_body_start)
                    first_line = content[method_body_start:next_line_end]
                    indentation = len(first_line) - len(first_line.lstrip())

                    # Add type checking code
                    type_check_code = (
                        " " * indentation
                        + "# Ensure input is float32 (required by ONNX)\n"
                    )
                    type_check_code += (
                        " " * indentation
                        + "if face_img is not None and face_img.dtype != np.float32:\n"
                    )
                    type_check_code += (
                        " " * indentation
                        + "    face_img = face_img.astype(np.float32)\n\n"
                    )

                    # Insert the code at the start of the method body
                    content = (
                        content[:method_body_start]
                        + type_check_code
                        + content[method_body_start:]
                    )
                    logger.info(
                        "Added data type checking to compute_embedding in core recognizer"
                    )

        # Write the updated content back to the file
        with open(recognizer_path, "w") as f:
            f.write(content)

        logger.info(f"Successfully updated {recognizer_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to fix core recognizer: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main function to apply all fixes."""
    print_header("ChromaDB Face Recognition Fix")

    # Verify ChromaDB is installed
    try:
        import chromadb

        version = chromadb.__version__
        logger.info(f"ChromaDB version: {version}")
    except ImportError:
        logger.error(
            "ChromaDB is not installed. Please install it with: pip install chromadb>=0.4.18"
        )
        return 1

    # Apply fixes
    fixes = [
        ("Fix data types in ChromaDB backend", fix_data_types),
        ("Fix core recognizer", fix_core_recognizer),
    ]

    success_count = 0
    for name, fix_fn in fixes:
        logger.info(f"Applying fix: {name}")
        try:
            if fix_fn():
                logger.info(f"✅ Successfully applied: {name}")
                success_count += 1
            else:
                logger.error(f"❌ Failed to apply: {name}")
        except Exception as e:
            logger.error(f"❌ Error applying {name}: {e}")
            import traceback

            traceback.print_exc()

    # Print summary
    print_header("Summary")
    print(f"Applied {success_count}/{len(fixes)} fixes successfully")

    if success_count == len(fixes):
        print("\nAll fixes applied successfully!")
        print("\nTo test the fixes, run:")
        print("  python -m src.main --recognizer-backend chromadb --debug")
    else:
        print(f"\n{len(fixes) - success_count} fixes failed to apply.")

    return 0 if success_count == len(fixes) else 1


if __name__ == "__main__":
    sys.exit(main())
