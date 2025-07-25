#!/usr/bin/env python3
"""
Test EmbeddingPathManager functionality and validate embedding file consistency
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append("src")

from embedding_path_manager import EmbeddingPathManager


def test_embedding_path_manager():
    """Test the EmbeddingPathManager functionality"""

    print("🧪 Testing EmbeddingPathManager...")

    # Initialize manager
    photo_dir = Path("../source/photo/contestants")
    path_manager = EmbeddingPathManager(photo_dir)

    print(f"\n📁 Photo directory: {photo_dir}")
    print(f"📁 Current naming convention: {path_manager.current_naming}")

    # Test path resolution for a few contestants
    print("\n📋 Testing path resolution:")
    test_contestants = [("1", "Ivy So"), ("2", "咖喱"), ("21", "Ling"), ("96", "3 妹")]

    for contestant_id, nickname in test_contestants:
        print(f"\n👤 Contestant {contestant_id} ({nickname}):")

        # Get standard paths
        emb_path, meta_path = path_manager.get_embedding_paths(contestant_id, nickname)
        print(f"   Standard embedding: {emb_path.name}")
        print(f"   Standard metadata: {meta_path.name}")

        # Find existing paths
        existing_emb, existing_meta = path_manager.find_existing_embedding_paths(
            contestant_id, nickname
        )
        if existing_emb:
            print(f"   ✅ Found embedding: {existing_emb.name}")
            print(
                f"   ✅ Found metadata: {existing_meta.name if existing_meta else 'None'}"
            )
        else:
            print("   ❌ No embedding found")

    # Validate overall consistency
    print("\n🔍 Validating embedding consistency:")
    validation_results = path_manager.validate_embedding_consistency()

    print(f"   Total embeddings: {validation_results['total_embeddings']}")
    print(f"   ID-based naming: {validation_results['id_based_naming']}")
    print(f"   Nickname-based naming: {validation_results['nickname_based_naming']}")
    print(f"   Missing metadata: {len(validation_results['missing_metadata'])}")

    if validation_results["missing_metadata"]:
        print(
            f"   Files missing metadata: {validation_results['missing_metadata'][:3]}..."
        )

    # List some embeddings
    print("\n📝 Sample embedding files:")
    all_embeddings = path_manager.list_all_embeddings()

    # Show first 5 embeddings
    for i, emb_info in enumerate(all_embeddings[:5]):
        status = "✅" if emb_info["has_metadata"] else "⚠️"
        unified = "unified" if emb_info["is_unified"] else "legacy"
        print(
            f"   {status} {emb_info['file_name']} ({unified}, {emb_info['naming_convention']})"
        )

    if len(all_embeddings) > 5:
        print(f"   ... and {len(all_embeddings) - 5} more")

    # Show statistics
    id_based_count = sum(
        1 for e in all_embeddings if e["naming_convention"] == "id_based"
    )
    unified_count = sum(1 for e in all_embeddings if e["is_unified"])
    with_metadata_count = sum(1 for e in all_embeddings if e["has_metadata"])

    print("\n📊 Statistics:")
    print(f"   📁 Total embedding files: {len(all_embeddings)}")
    print(f"   🆔 ID-based naming: {id_based_count}")
    print(f"   🔄 Unified embeddings: {unified_count}")
    print(f"   📋 With metadata: {with_metadata_count}")

    # Test photo path resolution
    print("\n📷 Testing photo path resolution:")
    photo_paths = path_manager.get_photo_paths("1", "Ivy So", "蘇雅琳")
    if photo_paths:
        print(f"   ✅ Found {len(photo_paths)} photo(s) for contestant 1:")
        for photo_path in photo_paths[:3]:
            print(f"      📸 {photo_path}")
    else:
        print("   ❌ No photos found for contestant 1")

    print("\n✅ EmbeddingPathManager test completed!")

    return True


if __name__ == "__main__":
    test_embedding_path_manager()
