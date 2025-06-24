"""
Contestant management service.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from app.core.config import get_settings
from app.models.schemas import Contestant


class ContestantService:
    """Service for contestant management."""
    
    def __init__(self):
        self.settings = get_settings()
        self.contestants_dir = Path(self.settings.contestants_dir)
    
    async def get_all_contestants(self) -> List[Contestant]:
        """Get list of all contestants."""
        contestants = []
        
        if not self.contestants_dir.exists():
            return contestants
        
        for contestant_dir in self.contestants_dir.iterdir():
            if contestant_dir.is_dir() and contestant_dir.name.isdigit():
                try:
                    contestant = await self._load_contestant(contestant_dir)
                    if contestant:
                        contestants.append(contestant)
                except Exception:
                    continue
        
        return sorted(contestants, key=lambda x: int(x.id) if x.id.isdigit() else 999)
    
    async def get_contestant(self, contestant_id: str) -> Optional[Contestant]:
        """Get specific contestant information."""
        contestant_dir = self.contestants_dir / contestant_id
        
        if not contestant_dir.exists():
            return None
        
        return await self._load_contestant(contestant_dir)
    
    async def _load_contestant(self, contestant_dir: Path) -> Optional[Contestant]:
        """Load contestant data from directory."""
        try:
            # Get photos
            photos = []
            for photo_file in contestant_dir.iterdir():
                if photo_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    photos.append(str(photo_file))
            
            # Check for embedding
            embedding_files = list(contestant_dir.glob('*.npy'))
            has_embedding = len(embedding_files) > 0
            
            # Try to find name from embedding file or use directory name
            name = contestant_dir.name
            for embedding_file in embedding_files:
                if embedding_file.stem != contestant_dir.name:
                    name = embedding_file.stem.replace('_embedding', '')
                    break
            
            return Contestant(
                id=contestant_dir.name,
                name=name,
                photos=photos,
                embedding_available=has_embedding
            )
            
        except Exception:
            return None
    
    async def get_contestant_photos(self, contestant_id: str) -> Optional[List[str]]:
        """Get contestant photo URLs."""
        contestant = await self.get_contestant(contestant_id)
        return contestant.photos if contestant else None
    
    async def refresh_embeddings(self) -> Dict[str, Any]:
        """Refresh face embeddings for all contestants."""
        # Placeholder implementation
        return {
            "processed": 0,
            "errors": []
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get contestant statistics."""
        contestants = await self.get_all_contestants()
        
        total_contestants = len(contestants)
        with_embeddings = sum(1 for c in contestants if c.embedding_available)
        
        return {
            "total_contestants": total_contestants,
            "contestants_with_embeddings": with_embeddings,
            "embedding_coverage": with_embeddings / total_contestants if total_contestants > 0 else 0
        }