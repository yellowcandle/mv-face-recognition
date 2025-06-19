#!/usr/bin/env python3
"""
Script to create a consolidated embeddings package for HF Spaces deployment.
Converts individual .npy files to a single JSON package to avoid Git LFS issues.
"""

import os
import json
import numpy as np
import pandas as pd
from pathlib import Path

def create_embeddings_package():
    """Create consolidated embeddings package from individual .npy files."""
    print("🔄 Creating embeddings package for HF Spaces deployment...")
    
    # Setup paths
    project_root = Path(__file__).parent.parent
    contestants_dir = project_root / "source/photo/contestants"
    output_file = project_root / "embeddings_package.json"
    csv_file = project_root / "contestant_info.csv"
    
    if not contestants_dir.exists():
        raise FileNotFoundError(f"Contestants directory not found: {contestants_dir}")
    
    if not csv_file.exists():
        raise FileNotFoundError(f"Contestant info CSV not found: {csv_file}")
    
    # Load contestant information
    try:
        contestant_info = pd.read_csv(csv_file)
        print(f"✅ Loaded contestant info: {len(contestant_info)} contestants")
    except Exception as e:
        print(f"❌ Failed to load contestant info: {e}")
        return False
    
    # Find all .npy embedding files
    embedding_files = list(contestants_dir.glob("*_embedding.npy"))
    print(f"📊 Found {len(embedding_files)} embedding files")
    
    if not embedding_files:
        print("⚠️ No embedding files found!")
        return False
    
    # Create the package
    package = {
        "version": "1.0",
        "created_by": "MV Face Recognition System",
        "description": "Consolidated face embeddings for HF Spaces deployment",
        "total_contestants": len(contestant_info),
        "total_embeddings": len(embedding_files),
        "embedding_dim": 512,  # InsightFace standard
        "contestants": [],
        "embeddings": {}
    }
    
    # Add contestant information
    for _, row in contestant_info.iterrows():
        package["contestants"].append({
            "id": int(row["編號"]),
            "name": str(row["姓名"]),
            "nickname": str(row["暱稱"]),
            "age": str(row["年齡"])
        })
    
    # Process embedding files
    successful_embeddings = 0
    for embedding_file in embedding_files:
        try:
            # Extract name from filename (remove _embedding.npy)
            contestant_name = embedding_file.stem.replace("_embedding", "")
            
            # Load embedding
            embedding = np.load(embedding_file, allow_pickle=True)
            
            # Handle different embedding formats
            if embedding.ndim > 1:
                # If multiple embeddings, take the mean
                embedding = np.mean(embedding, axis=0)
            
            # Ensure it's the right shape and type
            embedding = embedding.flatten().astype(np.float32)
            
            if len(embedding) != 512:
                print(f"⚠️ Unexpected embedding size for {contestant_name}: {len(embedding)}")
                continue
            
            # Convert to list for JSON serialization
            package["embeddings"][contestant_name] = embedding.tolist()
            successful_embeddings += 1
            
            print(f"✅ Processed {contestant_name}: {len(embedding)} dimensions")
            
        except Exception as e:
            print(f"❌ Failed to process {embedding_file.name}: {e}")
            continue
    
    print(f"📦 Successfully processed {successful_embeddings}/{len(embedding_files)} embeddings")
    
    # Save the package
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(package, f, ensure_ascii=False, indent=2)
        
        # Check file size
        file_size = output_file.stat().st_size
        print(f"💾 Created embeddings package: {output_file}")
        print(f"📊 Package size: {file_size / 1024:.1f} KB")
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            print("⚠️ Package is quite large - consider compression if needed")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to save package: {e}")
        return False

if __name__ == "__main__":
    success = create_embeddings_package()
    if success:
        print("🎉 Embeddings package created successfully!")
    else:
        print("💥 Failed to create embeddings package!")
        exit(1)