#!/usr/bin/env python3
"""
Create ChromaDB from embeddings package for HF Spaces deployment.
This script initializes ChromaDB with embeddings from the embeddings_package.json file.
"""

import json
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def initialize_chromadb_from_package(
    package_path: str = "embeddings_package.json",
    chroma_path: str = ".chroma_db"
) -> bool:
    """
    Initialize ChromaDB from embeddings package.
    
    Args:
        package_path: Path to the embeddings package JSON file
        chroma_path: Path where ChromaDB should be created
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Import ChromaDB
        import chromadb
        from chromadb.config import Settings
        
        logger.info(f"Loading embeddings package from: {package_path}")
        
        # Load the embeddings package
        with open(package_path, 'r', encoding='utf-8') as f:
            package_data = json.load(f)
        
        embeddings_data = package_data.get('embeddings', {})
        if not embeddings_data:
            logger.error("No embeddings found in package")
            return False
        
        logger.info(f"Found {len(embeddings_data)} contestants in package")
        
        # Create ChromaDB client
        Path(chroma_path).mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(
                allow_reset=True,
                anonymized_telemetry=False,
                is_persistent=True
            )
        )
        
        # Create or get collection
        try:
            # Try to delete existing collection first
            client.delete_collection("contestants")
        except:
            pass  # Collection might not exist
        
        collection = client.create_collection(
            name="contestants",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Prepare data for bulk insertion
        embeddings_list = []
        metadatas_list = []
        ids_list = []
        
        embedding_count = 0
        for contestant_name, contestant_embeddings in embeddings_data.items():
            for i, embedding_data in enumerate(contestant_embeddings):
                embedding_vector = embedding_data['embedding']
                
                # Validate embedding
                if not isinstance(embedding_vector, list) or len(embedding_vector) == 0:
                    logger.warning(f"Invalid embedding for {contestant_name}[{i}]")
                    continue
                
                # Normalize embedding
                embedding_array = np.array(embedding_vector, dtype=np.float32)
                norm = np.linalg.norm(embedding_array)
                if norm > 0:
                    embedding_array = embedding_array / norm
                else:
                    logger.warning(f"Zero-norm embedding for {contestant_name}[{i}]")
                    continue
                
                embeddings_list.append(embedding_array.tolist())
                metadatas_list.append({
                    "name": contestant_name,
                    "source": embedding_data.get('source', 'unknown'),
                    "confidence": embedding_data.get('confidence', 1.0)
                })
                ids_list.append(f"{contestant_name}_{i}")
                embedding_count += 1
        
        if not embeddings_list:
            logger.error("No valid embeddings to add to ChromaDB")
            return False
        
        # Bulk add to collection
        logger.info(f"Adding {len(embeddings_list)} embeddings to ChromaDB...")
        collection.add(
            embeddings=embeddings_list,
            metadatas=metadatas_list,
            ids=ids_list
        )
        
        # Verify the collection
        collection_count = collection.count()
        logger.info(f"✅ ChromaDB initialized with {collection_count} embeddings")
        
        return True
        
    except ImportError as e:
        logger.error(f"ChromaDB not available: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = initialize_chromadb_from_package()
    if success:
        print("✅ ChromaDB initialization completed successfully")
    else:
        print("❌ ChromaDB initialization failed")