import chromadb
from chromadb.config import Settings
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def get_chroma_client():
    """Get ChromaDB client with HF Spaces compatibility."""
    # Try multiple possible paths for ChromaDB data
    possible_paths = [
        ".chroma_db",  # Default local path
        "cache/chromadb",  # Alternative cache path
        "/tmp/chroma_db",  # Hugging Face Spaces temp path
    ]
    
    chroma_path = None
    for path in possible_paths:
        if Path(path).exists() and any(Path(path).iterdir()):
            chroma_path = path
            logger.info(f"Found ChromaDB data at: {path}")
            break
    
    if chroma_path is None:
        # Create new ChromaDB in temp directory for HF Spaces
        chroma_path = "/tmp/chroma_db" if os.path.exists("/tmp") else ".chroma_db"
        logger.info(f"Creating new ChromaDB at: {chroma_path}")
    
    try:
        return chromadb.PersistentClient(
            path=chroma_path, 
            settings=Settings(
                allow_reset=True,
                anonymized_telemetry=False,  # Disable telemetry for HF Spaces
                is_persistent=True
            )
        )
    except Exception as e:
        logger.error(f"Failed to create ChromaDB client: {e}")
        raise


def get_contestant_collection():
    """Get or create the contestants collection with error handling."""
    try:
        client = get_chroma_client()
        return client.get_or_create_collection(
            name="contestants",
            metadata={"hnsw:space": "cosine"},  # Optimized for face recognition
        )
    except Exception as e:
        logger.error(f"Failed to get contestant collection: {e}")
        raise
