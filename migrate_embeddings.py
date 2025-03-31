import os
import numpy as np
from chroma_db import get_contestant_collection

def migrate_npy_to_chroma():
    collection = get_contestant_collection()
    for root, _, files in os.walk("source/photo/contestants"):
        for file in files:
            if file.endswith("_embedding.npy"):
                emb = np.load(os.path.join(root, file))
                contestant_id = os.path.basename(root)
                contestant_name = file.split('_')[0]
                
                collection.add(
                    embeddings=[emb.tolist()],
                    metadatas=[{"name": contestant_name}],
                    ids=[contestant_id]
                )

if __name__ == "__main__":
    migrate_npy_to_chroma()
