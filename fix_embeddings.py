#!/usr/bin/env python3
"""
Fix embeddings database for MV Face Recognition.
Downloads, verifies, and refreshes the face embeddings database.
"""

import argparse
import logging
import sys
from pathlib import Path
import numpy as np
import subprocess
from typing import Dict, List, Tuple

# Add src to path
sys.path.append('src')

from src.database.chroma_setup import ChromaDBManager
from src.core.face_matcher import FaceMatcher

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_git_lfs() -> bool:
    """Check if git LFS is available and properly configured."""
    try:
        result = subprocess.run(['git', 'lfs', 'version'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Git LFS available: {result.stdout.strip()}")
            return True
        else:
            logger.error("Git LFS not available")
            return False
    except FileNotFoundError:
        logger.error("Git LFS not installed")
        return False


def pull_lfs_files() -> bool:
    """Pull LFS files to get actual embeddings."""
    try:
        logger.info("Pulling Git LFS files...")
        result = subprocess.run(['git', 'lfs', 'pull'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Git LFS pull successful")
            if result.stdout:
                logger.info(f"Output: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"Git LFS pull failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error pulling LFS files: {e}")
        return False


def verify_embedding_files() -> Dict[str, any]:
    """Verify all embedding files are valid numpy arrays."""
    contestants_dir = Path("source/photo/contestants")
    results = {
        'total_files': 0,
        'valid_files': 0,
        'invalid_files': [],
        'file_details': {},
        'total_embeddings': 0
    }
    
    if not contestants_dir.exists():
        logger.error(f"Contestants directory not found: {contestants_dir}")
        return results
    
    embedding_files = list(contestants_dir.glob("*_embedding.npy"))
    results['total_files'] = len(embedding_files)
    
    logger.info(f"Found {len(embedding_files)} embedding files")
    
    for file_path in embedding_files:
        try:
            # Check if it's a git LFS pointer
            if file_path.stat().st_size < 1000:  # LFS pointers are typically < 200 bytes
                with open(file_path, 'r') as f:
                    content = f.read()
                if 'git-lfs.github.com' in content:
                    logger.warning(f"File {file_path.name} is still a Git LFS pointer")
                    results['invalid_files'].append(f"{file_path.name} (Git LFS pointer)")
                    continue
            
            # Try to load as numpy array
            embedding = np.load(file_path)
            
            # Verify shape and type
            if embedding.shape == (1, 512) or embedding.shape == (512,):
                # Flatten if needed
                if embedding.ndim == 2:
                    embedding = embedding.flatten()
                
                results['valid_files'] += 1
                results['total_embeddings'] += 1
                
                # Store file details
                contestant_name = file_path.stem.replace('_embedding', '')
                results['file_details'][contestant_name] = {
                    'shape': embedding.shape,
                    'dtype': str(embedding.dtype),
                    'range': f"{embedding.min():.3f} to {embedding.max():.3f}",
                    'norm': f"{np.linalg.norm(embedding):.3f}",
                    'file_size': file_path.stat().st_size
                }
                
                logger.debug(f"✅ {file_path.name}: shape={embedding.shape}, dtype={embedding.dtype}")
                
            else:
                logger.error(f"❌ {file_path.name}: Invalid shape {embedding.shape}, expected (512,) or (1, 512)")
                results['invalid_files'].append(f"{file_path.name} (invalid shape: {embedding.shape})")
                
        except Exception as e:
            logger.error(f"❌ {file_path.name}: Error loading - {e}")
            results['invalid_files'].append(f"{file_path.name} (load error: {e})")
    
    return results


def refresh_chromadb(force: bool = False) -> bool:
    """Refresh ChromaDB with verified embeddings."""
    try:
        logger.info("Refreshing ChromaDB...")
        
        # Initialize ChromaDB manager
        db_manager = ChromaDBManager()
        
        # Get current stats
        current_stats = db_manager.get_database_stats()
        logger.info(f"Current database stats: {current_stats}")
        
        if force or current_stats['total_embeddings'] == 0:
            # Repopulate database
            count = db_manager.populate_database(force_refresh=force)
            logger.info(f"Database populated with {count} embeddings")
            
            # Get new stats
            new_stats = db_manager.get_database_stats()
            logger.info(f"New database stats: {new_stats}")
            
            return True
        else:
            logger.info("Database already populated. Use --force to refresh.")
            return True
            
    except Exception as e:
        logger.error(f"Error refreshing ChromaDB: {e}")
        return False


def test_face_matching() -> bool:
    """Test face matching with sample embeddings."""
    try:
        logger.info("Testing face matching...")
        
        # Initialize face matcher
        matcher = FaceMatcher()
        
        # Get a sample embedding
        contestants_dir = Path("source/photo/contestants")
        embedding_files = list(contestants_dir.glob("*_embedding.npy"))
        
        if not embedding_files:
            logger.error("No embedding files found for testing")
            return False
        
        # Test with first embedding file
        test_file = embedding_files[0]
        expected_name = test_file.stem.replace('_embedding', '')
        
        embedding = np.load(test_file)
        if embedding.ndim == 2:
            embedding = embedding.flatten()
        
        logger.info(f"Testing with {test_file.name}, expected name: '{expected_name}'")
        logger.info(f"Embedding shape: {embedding.shape}, norm: {np.linalg.norm(embedding):.3f}")
        
        # Test detailed matching to see what's happening
        details = matcher.match_with_details(embedding)
        logger.info(f"Detailed match result: {details}")
        
        # Also test direct ChromaDB search
        matches = matcher.db_manager.search_similar_faces(embedding, n_results=5)
        logger.info(f"Direct ChromaDB search results: {matches}")
        
        # Test matching
        match = matcher.match_face(embedding)
        
        if match:
            name, similarity = match
            logger.info(f"✅ Test match successful: {name} (similarity: {similarity:.3f})")
            
            if name == expected_name:
                logger.info(f"✅ Correct match: Expected '{expected_name}', got '{name}'")
            else:
                logger.warning(f"⚠️ Different match: Expected '{expected_name}', got '{name}'")
            
            if similarity > 0.5:
                logger.info(f"✅ Good similarity score: {similarity:.3f}")
            else:
                logger.warning(f"⚠️ Low similarity score: {similarity:.3f}")
            
            return True
        else:
            logger.error("❌ No match found - this indicates a problem with the database")
            return False
            
    except Exception as e:
        logger.error(f"Error testing face matching: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def print_summary_report(verification_results: Dict, db_refresh_success: bool, matching_success: bool):
    """Print a comprehensive summary report."""
    print("\n" + "="*60)
    print("🔍 EMBEDDINGS DATABASE DIAGNOSTIC REPORT")
    print("="*60)
    
    # File verification summary
    print(f"\n📁 Embedding Files:")
    print(f"  Total files found: {verification_results['total_files']}")
    print(f"  Valid embeddings: {verification_results['valid_files']}")
    print(f"  Invalid files: {len(verification_results['invalid_files'])}")
    
    if verification_results['invalid_files']:
        print(f"\n❌ Invalid files:")
        for invalid in verification_results['invalid_files']:
            print(f"    - {invalid}")
    
    # Database status
    print(f"\n🗄️ Database Status:")
    print(f"  ChromaDB refresh: {'✅ Success' if db_refresh_success else '❌ Failed'}")
    print(f"  Face matching test: {'✅ Success' if matching_success else '❌ Failed'}")
    
    # Sample file details
    if verification_results['file_details']:
        print(f"\n📊 Sample Embedding Details:")
        for name, details in list(verification_results['file_details'].items())[:3]:
            print(f"  {name}:")
            print(f"    Shape: {details['shape']}")
            print(f"    Type: {details['dtype']}")
            print(f"    Range: {details['range']}")
            print(f"    Norm: {details['norm']}")
    
    # Overall status
    overall_success = (
        verification_results['valid_files'] > 0 and
        db_refresh_success and
        matching_success
    )
    
    print(f"\n🎯 Overall Status: {'✅ SUCCESS' if overall_success else '❌ ISSUES DETECTED'}")
    
    if overall_success:
        print("Face recognition should now work correctly!")
    else:
        print("Issues detected. Check the logs above for details.")
    
    print("="*60)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Fix embeddings database for face recognition')
    parser.add_argument('--pull', action='store_true', help='Pull Git LFS files')
    parser.add_argument('--verify', action='store_true', help='Verify embedding files')
    parser.add_argument('--refresh', action='store_true', help='Refresh ChromaDB')
    parser.add_argument('--test', action='store_true', help='Test face matching')
    parser.add_argument('--force', action='store_true', help='Force refresh even if database exists')
    parser.add_argument('--all', action='store_true', help='Run all operations')
    
    args = parser.parse_args()
    
    # If no specific operation, run all
    if not any([args.pull, args.verify, args.refresh, args.test]):
        args.all = True
    
    print("🔧 MV Face Recognition - Embeddings Database Fix")
    print("="*50)
    
    verification_results = {}
    db_refresh_success = False
    matching_success = False
    
    # Step 1: Pull LFS files if requested
    if args.all or args.pull:
        if check_git_lfs():
            pull_lfs_files()
        else:
            logger.warning("Git LFS not available, skipping pull")
    
    # Step 2: Verify embedding files
    if args.all or args.verify:
        verification_results = verify_embedding_files()
        
        if verification_results['valid_files'] > 0:
            logger.info(f"✅ Found {verification_results['valid_files']} valid embedding files")
        else:
            logger.error("❌ No valid embedding files found")
            return False
    
    # Step 3: Refresh database
    if args.all or args.refresh:
        db_refresh_success = refresh_chromadb(force=args.force)
    
    # Step 4: Test face matching
    if args.all or args.test:
        matching_success = test_face_matching()
    
    # Print summary report
    if args.all:
        print_summary_report(verification_results, db_refresh_success, matching_success)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)