import chromadb
from chromadb.config import Settings

def get_chroma_client():
    return chromadb.Client(Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory=".chroma_db" 
    ))

def get_contestant_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="contestants",
        metadata={"hnsw:space": "cosine"}  # Optimized for face recognition
    )
