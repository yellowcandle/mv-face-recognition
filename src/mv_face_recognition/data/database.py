import chromadb
from chromadb.config import Settings


def get_chroma_client():
    return chromadb.PersistentClient(
        path=".chroma_db", settings=Settings(allow_reset=True)
    )


def get_contestant_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="contestants",
        metadata={"hnsw:space": "cosine"},  # Optimized for face recognition
    )
