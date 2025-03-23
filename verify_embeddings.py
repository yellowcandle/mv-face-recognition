#!/usr/bin/env python
"""
Embedding Verification Script

This script verifies embedding dimensions across the dataset and ChromaDB collections.
It helps identify inconsistencies that might cause issues with the face recognition system.

Usage:
    python verify_embeddings.py
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Define colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class EmbeddingVerifier:
    def __init__(self):
        self.cache_dir = PROJECT_ROOT / "cache"
        self.chromadb_dir = self.cache_dir / "chromadb"
        self.embeddings_dir = self.cache_dir / "embeddings"
        self.stats = {
            "embeddings_checked": 0,
            "dimension_inconsistencies": 0,
            "format_issues": 0
        }
        
    def print_header(self, message):
        """Print a formatted header"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD} {message} {Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")

    def print_success(self, message):
        """Print a success message"""
        print(f"{Colors.GREEN}✓ SUCCESS: {message}{Colors.ENDC}")

    def print_warning(self, message):
        """Print a warning message"""
        print(f"{Colors.YELLOW}⚠ WARNING: {message}{Colors.ENDC}")

    def print_error(self, message):
        """Print an error message"""
        print(f"{Colors.RED}✗ ERROR: {message}{Colors.ENDC}")

    def print_info(self, message):
        """Print an info message"""
        print(f"ℹ {message}")
        
    def run_verification(self):
        """Run the full verification"""
        self.print_header("Face Embedding Verification Tool")
        
        print(f"Cache directory: {self.cache_dir}")
        print(f"ChromaDB directory: {self.chromadb_dir}")
        print(f"Embeddings directory: {self.embeddings_dir}")
        
        # Check if directories exist
        if not self.cache_dir.exists():
            self.print_error(f"Cache directory does not exist: {self.cache_dir}")
            return
            
        if not self.embeddings_dir.exists():
            self.print_warning(f"Embeddings directory does not exist: {self.embeddings_dir}")
        else:
            self.verify_cached_embeddings()
            
        # Try to import chromadb
        try:
            import chromadb
            self.print_success(f"ChromaDB is installed (version: {chromadb.__version__})")
            self.verify_chromadb_collections()
        except ImportError:
            self.print_error("ChromaDB is not installed, skipping collection verification")
            
        # Print summary
        self.print_header("Verification Summary")
        print(f"Embeddings checked: {self.stats['embeddings_checked']}")
        print(f"Dimension inconsistencies: {self.stats['dimension_inconsistencies']}")
        print(f"Format issues: {self.stats['format_issues']}")
        
        if self.stats['dimension_inconsistencies'] > 0:
            self.print_error("Found embedding dimension inconsistencies!")
            print("\nPossible solutions:")
            print("1. Clear the ChromaDB database: rm -rf cache/chromadb/*")
            print("2. Regenerate embeddings with consistent model settings")
            print("3. Use the embedding dimension handling in ChromaDBFaceRecognizer")
        elif self.stats['format_issues'] > 0:
            self.print_warning("Found embedding format issues!")
            print("\nPossible solutions:")
            print("1. Check the embedding generation process")
            print("2. Ensure proper serialization/deserialization of embeddings")
        else:
            self.print_success("No embedding issues found!")
            
    def verify_cached_embeddings(self):
        """Verify cached embeddings in the filesystem"""
        self.print_header("Verifying Cached Embeddings")
        
        # Look for numpy files
        npy_files = list(self.embeddings_dir.glob("**/*.npy"))
        self.print_info(f"Found {len(npy_files)} .npy files")
        
        # Look for JSON files
        json_files = list(self.embeddings_dir.glob("**/*.json"))
        self.print_info(f"Found {len(json_files)} .json files")
        
        # Check dimensions of numpy files
        dimensions = {}
        
        for npy_file in npy_files:
            try:
                data = np.load(npy_file, allow_pickle=True)
                self.stats["embeddings_checked"] += 1
                
                # Handle different array shapes
                if isinstance(data, np.ndarray):
                    shape = data.shape
                    dims = shape[-1] if len(shape) > 1 else shape[0]
                    
                    if dims not in dimensions:
                        dimensions[dims] = []
                    dimensions[dims].append(npy_file.name)
                    
                else:
                    self.print_warning(f"File is not a numpy array: {npy_file}")
                    self.stats["format_issues"] += 1
                    
            except Exception as e:
                self.print_error(f"Failed to load {npy_file}: {str(e)}")
                self.stats["format_issues"] += 1
                
        # Check JSON files
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    self.stats["embeddings_checked"] += 1
                    
                # Check if it contains embeddings
                if isinstance(data, dict) and any(key for key in data.keys() if 'embedding' in key.lower()):
                    # Find embedding fields
                    for key, value in data.items():
                        if 'embedding' in key.lower():
                            if isinstance(value, list):
                                dims = len(value)
                                
                                if dims not in dimensions:
                                    dimensions[dims] = []
                                dimensions[dims].append(f"{json_file.name}:{key}")
                                
            except Exception as e:
                self.print_error(f"Failed to load {json_file}: {str(e)}")
                self.stats["format_issues"] += 1
                
        # Report dimensions
        self.print_info(f"Found {len(dimensions)} different embedding dimensions")
        
        for dims, files in dimensions.items():
            self.print_info(f"Dimension {dims}: {len(files)} embeddings")
            
        # Check for inconsistencies
        if len(dimensions) > 1:
            self.print_warning("Multiple embedding dimensions detected!")
            for dims, files in dimensions.items():
                print(f"  - Dimension {dims}: {len(files)} embeddings")
                # Show sample files
                for file in files[:3]:
                    print(f"    - {file}")
                if len(files) > 3:
                    print(f"    - ... and {len(files) - 3} more")
                    
            self.stats["dimension_inconsistencies"] += 1
        else:
            self.print_success("All cached embeddings have consistent dimensions")
            
    def verify_chromadb_collections(self):
        """Verify ChromaDB collections"""
        self.print_header("Verifying ChromaDB Collections")
        
        if not self.chromadb_dir.exists():
            self.print_error(f"ChromaDB directory does not exist: {self.chromadb_dir}")
            return
            
        try:
            import chromadb
            
            # Try to connect to persistent client
            try:
                client = chromadb.PersistentClient(path=str(self.chromadb_dir))
                self.print_success("Successfully connected to ChromaDB")
                
                # List collections
                collections = client.list_collections()
                self.print_info(f"Found {len(collections)} collections")
                
                # Check each collection
                for collection in collections:
                    self.print_info(f"Checking collection: {collection.name}")
                    
                    try:
                        # Get peek to determine dimensionality
                        peek = collection.peek(limit=1)
                        
                        if peek and 'embeddings' in peek and peek['embeddings']:
                            sample_embedding = peek['embeddings'][0]
                            dims = len(sample_embedding)
                            self.print_info(f"Collection {collection.name} has embedding dimension: {dims}")
                            
                            # Check more embeddings
                            count = collection.count()
                            self.stats["embeddings_checked"] += count
                            
                            if count > 1:
                                # Get another sample to verify consistency
                                query_results = collection.query(
                                    query_embeddings=[sample_embedding],
                                    n_results=min(count, 5)
                                )
                                
                                if query_results and 'embeddings' in query_results and query_results['embeddings']:
                                    # Check dimensions of results
                                    result_embeddings = query_results['embeddings'][0]
                                    for i, emb in enumerate(result_embeddings):
                                        if len(emb) != dims:
                                            self.print_error(f"Dimension mismatch in collection {collection.name}!")
                                            self.print_info(f"Expected {dims}, got {len(emb)}")
                                            self.stats["dimension_inconsistencies"] += 1
                                            break
                                    else:
                                        self.print_success(f"Sampled embeddings in collection {collection.name} have consistent dimensions")
                            
                        else:
                            self.print_warning(f"Collection {collection.name} appears to be empty")
                            
                    except Exception as e:
                        self.print_error(f"Error checking collection {collection.name}: {str(e)}")
                
            except Exception as e:
                self.print_error(f"Failed to connect to ChromaDB: {str(e)}")
                
        except Exception as e:
            self.print_error(f"Error during ChromaDB verification: {str(e)}")
            
if __name__ == "__main__":
    verifier = EmbeddingVerifier()
    verifier.run_verification()