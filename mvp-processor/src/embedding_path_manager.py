"""
Embedding Path Manager
Centralizes all embedding file path logic to prevent naming confusion
and provides consistent path resolution across all modules
"""

from pathlib import Path
from typing import Tuple, Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class EmbeddingPathManager:
    """
    Manages embedding file paths with support for both ID-based and nickname-based naming conventions
    Provides a central point for all embedding path resolution logic
    """
    
    def __init__(self, photo_dir: Path):
        self.photo_dir = Path(photo_dir)
        self.current_naming = "id_based"  # Current standard
        
    def get_embedding_paths(self, contestant_id: str, nickname: str) -> Tuple[Path, Path]:
        """
        Get embedding and metadata file paths for a contestant
        
        Args:
            contestant_id: Contestant ID (1-96)
            nickname: Contestant nickname
            
        Returns:
            Tuple of (embedding_path, metadata_path)
        """
        if self.current_naming == "id_based":
            embedding_path = self.photo_dir / f"contestant_{contestant_id}_unified_embedding.npy"
            metadata_path = self.photo_dir / f"contestant_{contestant_id}_embedding_metadata.json"
        else:
            # Legacy nickname-based naming
            embedding_path = self.photo_dir / f"{nickname}_unified_embedding.npy"
            metadata_path = self.photo_dir / f"{nickname}_embedding_metadata.json"
            
        return embedding_path, metadata_path
    
    def find_existing_embedding_paths(self, contestant_id: str, nickname: str) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Find existing embedding files using both naming conventions
        
        Args:
            contestant_id: Contestant ID (1-96)
            nickname: Contestant nickname
            
        Returns:
            Tuple of (embedding_path, metadata_path) if found, (None, None) if not found
        """
        
        # Try ID-based naming first (current standard)
        id_embedding_path = self.photo_dir / f"contestant_{contestant_id}_unified_embedding.npy"
        id_metadata_path = self.photo_dir / f"contestant_{contestant_id}_embedding_metadata.json"
        
        if id_embedding_path.exists() and id_metadata_path.exists():
            return id_embedding_path, id_metadata_path
        
        # Fallback to legacy nickname-based naming
        nickname_embedding_path = self.photo_dir / f"{nickname}_unified_embedding.npy"
        nickname_metadata_path = self.photo_dir / f"{nickname}_embedding_metadata.json"
        
        if nickname_embedding_path.exists() and nickname_metadata_path.exists():
            logger.debug(f"Found legacy embedding for {nickname} (ID: {contestant_id})")
            return nickname_embedding_path, nickname_metadata_path
        
        # Try other legacy patterns
        legacy_patterns = [
            (f"{contestant_id}_embedding.npy", f"{contestant_id}_embedding_metadata.json"),
            (f"{nickname}_embedding.npy", f"{nickname}_embedding_metadata.json"),
        ]
        
        for emb_pattern, meta_pattern in legacy_patterns:
            emb_path = self.photo_dir / emb_pattern
            meta_path = self.photo_dir / meta_pattern
            
            if emb_path.exists():
                # Found legacy embedding, may not have metadata
                metadata_path = meta_path if meta_path.exists() else None
                logger.debug(f"Found legacy embedding pattern for {nickname}: {emb_pattern}")
                return emb_path, metadata_path
        
        return None, None
    
    def get_photo_paths(self, contestant_id: str, nickname: str, name: str) -> List[Path]:
        """
        Get potential photo file paths for a contestant
        
        Args:
            contestant_id: Contestant ID (1-96) 
            nickname: Contestant nickname
            name: Contestant full name
            
        Returns:
            List of potential photo paths in order of preference
        """
        
        photo_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        photo_paths = []
        
        # Try contestant directory structure first
        contestant_dir = self.photo_dir / str(contestant_id)
        if contestant_dir.exists():
            for ext in photo_extensions:
                # Primary photo pattern: {id}-1.jpg
                primary_photo = contestant_dir / f"{contestant_id}-1{ext}"
                if primary_photo.exists():
                    photo_paths.append(primary_photo)
                
                # Secondary photos: {id}-2.jpg, etc.
                secondary_photo = contestant_dir / f"{contestant_id}-2{ext}"
                if secondary_photo.exists():
                    photo_paths.append(secondary_photo)
        
        # Try direct files in photo directory
        for ext in photo_extensions:
            # Try different naming patterns
            patterns = [
                f"{nickname}{ext}",
                f"{name}{ext}",
                f"{contestant_id}{ext}",
                f"contestant_{contestant_id}{ext}"
            ]
            
            for pattern in patterns:
                photo_path = self.photo_dir / pattern
                if photo_path.exists() and photo_path not in photo_paths:
                    photo_paths.append(photo_path)
        
        return photo_paths
    
    def migrate_to_standard_naming(self, contestant_id: str, nickname: str) -> bool:
        """
        Migrate embedding files to standard ID-based naming if needed
        
        Args:
            contestant_id: Contestant ID (1-96)
            nickname: Contestant nickname
            
        Returns:
            True if migration was performed, False if not needed
        """
        
        # Get standard paths
        standard_emb_path, standard_meta_path = self.get_embedding_paths(contestant_id, nickname)
        
        # If standard files already exist, no migration needed
        if standard_emb_path.exists() and standard_meta_path.exists():
            return False
        
        # Find existing files
        existing_emb_path, existing_meta_path = self.find_existing_embedding_paths(contestant_id, nickname)
        
        if existing_emb_path is None:
            return False  # No files to migrate
        
        try:
            # Move/copy embedding file
            if not standard_emb_path.exists():
                existing_emb_path.rename(standard_emb_path)
                logger.info(f"Migrated embedding for {nickname}: {existing_emb_path.name} -> {standard_emb_path.name}")
            
            # Move/copy metadata file if it exists
            if existing_meta_path and existing_meta_path.exists() and not standard_meta_path.exists():
                existing_meta_path.rename(standard_meta_path)
                logger.info(f"Migrated metadata for {nickname}: {existing_meta_path.name} -> {standard_meta_path.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate embedding files for {nickname}: {e}")
            return False
    
    def validate_embedding_consistency(self) -> Dict[str, any]:
        """
        Validate that all embedding files follow consistent naming
        
        Returns:
            Dictionary with validation results
        """
        
        results = {
            "total_embeddings": 0,
            "id_based_naming": 0,
            "nickname_based_naming": 0,
            "inconsistent_files": [],
            "missing_metadata": [],
            "orphaned_files": []
        }
        
        # Find all embedding files
        embedding_files = list(self.photo_dir.glob("*_embedding.npy")) + \
                         list(self.photo_dir.glob("*_unified_embedding.npy"))
        
        results["total_embeddings"] = len(embedding_files)
        
        for emb_file in embedding_files:
            if emb_file.name.startswith("contestant_"):
                results["id_based_naming"] += 1
            else:
                results["nickname_based_naming"] += 1
            
            # Check for corresponding metadata file
            if "unified_embedding" in emb_file.name:
                meta_file = emb_file.with_name(emb_file.name.replace("_unified_embedding.npy", "_embedding_metadata.json"))
            else:
                meta_file = emb_file.with_name(emb_file.name.replace("_embedding.npy", "_embedding_metadata.json"))
            
            if not meta_file.exists():
                results["missing_metadata"].append(emb_file.name)
        
        return results
    
    def list_all_embeddings(self) -> List[Dict[str, any]]:
        """
        List all embedding files with their details
        
        Returns:
            List of embedding file information dictionaries
        """
        
        embeddings = []
        
        # Find all embedding files
        embedding_files = list(self.photo_dir.glob("*_embedding.npy")) + \
                         list(self.photo_dir.glob("*_unified_embedding.npy"))
        
        for emb_file in embedding_files:
            info = {
                "file_path": emb_file,
                "file_name": emb_file.name,
                "size_bytes": emb_file.stat().st_size if emb_file.exists() else 0,
                "naming_convention": "id_based" if emb_file.name.startswith("contestant_") else "nickname_based",
                "is_unified": "unified_embedding" in emb_file.name,
                "has_metadata": False,
                "metadata_path": None
            }
            
            # Check for metadata file
            if "unified_embedding" in emb_file.name:
                meta_file = emb_file.with_name(emb_file.name.replace("_unified_embedding.npy", "_embedding_metadata.json"))
            else:
                meta_file = emb_file.with_name(emb_file.name.replace("_embedding.npy", "_embedding_metadata.json"))
            
            if meta_file.exists():
                info["has_metadata"] = True
                info["metadata_path"] = meta_file
            
            embeddings.append(info)
        
        # Sort by naming convention and file name
        embeddings.sort(key=lambda x: (x["naming_convention"], x["file_name"]))
        
        return embeddings