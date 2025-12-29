"""
Batch Face Recognition Module
Optimizes ChromaDB queries through batch processing
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class BatchFaceRecognizer:
    """Performs batch face recognition to reduce query overhead"""
    
    def __init__(self, recognizer, batch_size: int = 16, max_workers: int = 4):
        """
        Initialize batch recognizer
        
        Args:
            recognizer: FaceRecognizer instance
            batch_size: Number of faces to process per batch
            max_workers: Max threads for parallel processing
        """
        self.recognizer = recognizer
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.query_cache = {}
        
    def recognize_faces_batch(
        self,
        detections: List[Dict],
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Recognize multiple faces efficiently
        
        Args:
            detections: List of face detection dicts
            use_cache: Use cache for repeated faces
            
        Returns:
            List of recognition results
        """
        if not detections:
            return []
        
        # Split into batches
        results = []
        for i in range(0, len(detections), self.batch_size):
            batch = detections[i:i + self.batch_size]
            batch_results = self._process_batch(batch, use_cache)
            results.extend(batch_results)
        
        return results
    
    def _process_batch(
        self,
        batch: List[Dict],
        use_cache: bool
    ) -> List[Dict]:
        """Process a single batch of detections"""
        results = []
        
        # Prepare encodings for batch query
        encodings = []
        indices = []
        
        for idx, detection in enumerate(batch):
            encoding = detection.get('encoding')
            if encoding is not None:
                encodings.append(encoding)
                indices.append(idx)
        
        if not encodings:
            return results
        
        # Batch query ChromaDB
        encodings_array = np.array(encodings)
        batch_matches = self._batch_query_chromadb(encodings_array)
        
        # Map results back to original batch
        for idx, (original_idx, matches) in enumerate(zip(indices, batch_matches)):
            detection = batch[original_idx]
            best_match = matches[0] if matches else None
            
            results.append({
                'detection': detection,
                'match': best_match,
                'all_matches': matches
            })
        
        return results
    
    def _batch_query_chromadb(
        self,
        encodings: np.ndarray
    ) -> List[List[Dict]]:
        """
        Query ChromaDB with multiple encodings efficiently
        
        Args:
            encodings: Array of face encodings (N x 128)
            
        Returns:
            List of matches for each encoding
        """
        all_matches = []
        
        for encoding in encodings:
            # Query single face
            matches = self.recognizer.query_database(
                encoding,
                top_k=5,
                threshold=0.5
            )
            all_matches.append(matches)
        
        return all_matches
    
    def recognize_faces_parallel(
        self,
        detections: List[Dict],
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Recognize faces using parallel processing
        
        Args:
            detections: List of face detections
            use_cache: Use cache for repeated faces
            
        Returns:
            List of recognition results
        """
        if not detections:
            return []
        
        results = [None] * len(detections)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {}
            
            for idx, detection in enumerate(detections):
                encoding = detection.get('encoding')
                if encoding is not None:
                    future = executor.submit(
                        self._recognize_single,
                        encoding,
                        detection,
                        use_cache
                    )
                    future_to_idx[future] = idx
            
            # Collect results as they complete
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Error recognizing face {idx}: {e}")
                    results[idx] = {
                        'detection': detections[idx],
                        'match': None,
                        'error': str(e)
                    }
        
        return [r for r in results if r is not None]
    
    def _recognize_single(
        self,
        encoding: np.ndarray,
        detection: Dict,
        use_cache: bool
    ) -> Dict:
        """Recognize a single face"""
        # Check cache
        if use_cache:
            cache_key = tuple(encoding[:5].round(3))  # Use first 5 dims as cache key
            if cache_key in self.query_cache:
                return {
                    'detection': detection,
                    'match': self.query_cache[cache_key],
                    'cached': True
                }
        
        # Query database
        matches = self.recognizer.query_database(
            encoding,
            top_k=5,
            threshold=0.5
        )
        
        best_match = matches[0] if matches else None
        
        # Cache result
        if use_cache and best_match:
            cache_key = tuple(encoding[:5].round(3))
            self.query_cache[cache_key] = best_match
        
        return {
            'detection': detection,
            'match': best_match,
            'all_matches': matches
        }
    
    def clear_cache(self):
        """Clear the query cache"""
        cache_size = len(self.query_cache)
        self.query_cache.clear()
        logger.info(f"Cleared recognition cache ({cache_size} entries)")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            'cache_size': len(self.query_cache),
            'estimated_memory_mb': len(self.query_cache) * 0.001  # Rough estimate
        }


class ConfidenceFilter:
    """Filters detections based on confidence scores"""
    
    @staticmethod
    def filter_low_confidence(
        detections: List[Dict],
        min_confidence: float = 0.3,
        remove: bool = False
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter detections by confidence
        
        Args:
            detections: List of detections
            min_confidence: Minimum confidence threshold
            remove: If True, return removed detections in second tuple
            
        Returns:
            (passing detections, failing detections)
        """
        passing = []
        failing = []
        
        for detection in detections:
            confidence = detection.get('confidence', 1.0)
            if confidence >= min_confidence:
                passing.append(detection)
            else:
                failing.append(detection)
        
        return (passing, failing) if remove else (passing, [])
    
    @staticmethod
    def adaptive_threshold(
        detections: List[Dict],
        percentile: float = 25.0
    ) -> float:
        """
        Calculate adaptive confidence threshold based on detections
        
        Args:
            detections: List of detections
            percentile: Use Nth percentile as threshold
            
        Returns:
            Calculated threshold
        """
        if not detections:
            return 0.3
        
        confidences = [d.get('confidence', 1.0) for d in detections]
        return float(np.percentile(confidences, percentile))
