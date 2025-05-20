#!/usr/bin/env python
"""
ChromaDB Backend Debugging Script

This script provides detailed debugging for ChromaDB-specific issues in the face recognition system.
It checks the database connection, validates embeddings, and tests basic functionality.

Usage:
    python debug_chromadb.py

This script will test:
1. ChromaDB installation and version
2. Database connection
3. Embedding storage and retrieval
4. Collection integrity
5. Query functionality
"""

import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

# Set up project root path
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configuration
CACHE_DIR = PROJECT_ROOT / "cache" / "chromadb"
COLLECTION_NAME = "face_embeddings"
TEST_EMBEDDING_DIM = 512  # Standard dimension for face embeddings


def print_section(title):
    """Print a section divider with title."""
    print("\n" + "=" * 50)
    print(f" {title} ".center(50, "-"))
    print("=" * 50)


def check_chromadb_installation():
    """Check if ChromaDB is installed and get version information."""
    print_section("ChromaDB Installation Check")

    try:
        import chromadb

        print(f"✅ ChromaDB is installed (version: {chromadb.__version__})")

        # Check version compatibility
        version = chromadb.__version__.split(".")
        major, minor = int(version[0]), int(version[1])
        if major == 0 and minor < 4:
            print(f"⚠️ Warning: ChromaDB version {chromadb.__version__} may be too old.")
            print("   Recommended version is 0.4.18 or higher")

        # Print more info about the installation
        print("\nChromaDB Configuration:")
        print(f"- Default Persistence directory: {chromadb.Settings.persist_directory}")

        return True
    except ImportError:
        print("❌ ChromaDB is not installed")
        print("   Install with: pip install chromadb>=0.4.18")
        return False
    except Exception as e:
        print(f"❌ Error checking ChromaDB installation: {str(e)}")
        traceback.print_exc()
        return False


def check_database_connection():
    """Check connection to ChromaDB and create a test collection."""
    print_section("ChromaDB Connection Test")

    try:
        import chromadb

        # Try persistent client first
        print("Testing persistent ChromaDB client...")
        persistent_client = None

        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            persistent_client = chromadb.PersistentClient(path=str(CACHE_DIR))
            print(f"✅ Successfully connected to persistent ChromaDB at {CACHE_DIR}")

            # List existing collections
            collections = persistent_client.list_collections()
            print(f"Found {len(collections)} existing collections:")
            for coll in collections:
                print(f"  - {coll.name}: {coll.count()} items")
        except Exception as e:
            print(f"❌ Error connecting to persistent ChromaDB: {str(e)}")
            print("   Will try in-memory client instead")

        # Try in-memory client
        if not persistent_client:
            memory_client = chromadb.Client()
            print("✅ Successfully connected to in-memory ChromaDB")

        return True
    except Exception as e:
        print(f"❌ Error connecting to ChromaDB: {str(e)}")
        traceback.print_exc()
        return False


def test_embedding_operations():
    """Test basic embedding storage and retrieval operations."""
    print_section("ChromaDB Embedding Operations Test")

    try:
        import chromadb

        # Create in-memory client for testing
        client = chromadb.Client()

        # Create test collection
        test_collection = client.create_collection(name="test_collection")
        print("✅ Created test collection")

        # Generate random test embedding
        test_embedding = np.random.rand(TEST_EMBEDDING_DIM).tolist()
        test_id = "test_face_123"
        test_metadata = {"person_id": "test_person", "confidence": 0.95}

        # Add embedding
        test_collection.add(
            embeddings=[test_embedding],
            documents=["Test face embedding"],
            metadatas=[test_metadata],
            ids=[test_id],
        )
        print("✅ Successfully added test embedding")

        # Query the embedding
        results = test_collection.query(query_embeddings=[test_embedding], n_results=5)

        if results["ids"] and test_id in results["ids"][0]:
            print("✅ Successfully queried and retrieved test embedding")
        else:
            print("❌ Failed to retrieve test embedding")

        return True
    except Exception as e:
        print(f"❌ Error testing embedding operations: {str(e)}")
        traceback.print_exc()
        return False


def check_existing_data():
    """Check existing embedding data in ChromaDB."""
    print_section("ChromaDB Existing Data Check")

    try:
        import chromadb

        # Skip if cache directory doesn't exist
        if not CACHE_DIR.exists():
            print("⚠️ Cache directory doesn't exist, skipping data check.")
            return True

        # Connect to the persistent database
        client = chromadb.PersistentClient(path=str(CACHE_DIR))

        # Check if the collection exists
        collections = client.list_collections()
        collection_names = [c.name for c in collections]

        if COLLECTION_NAME not in collection_names:
            print(f"⚠️ Collection '{COLLECTION_NAME}' not found. Available collections:")
            for name in collection_names:
                print(f"  - {name}")
            return True

        # Get the face embeddings collection
        collection = client.get_collection(COLLECTION_NAME)
        count = collection.count()
        print(f"✅ Found collection '{COLLECTION_NAME}' with {count} embeddings")

        if count > 0:
            # Get a sample of embeddings
            sample_size = min(5, count)
            # Get sample using peek method if available, otherwise get all
            try:
                sample = collection.peek(sample_size)
            except AttributeError:
                # For older versions that don't have peek
                all_ids = collection.get()["ids"]
                sample_ids = all_ids[:sample_size]
                sample = collection.get(ids=sample_ids)

            print(f"\nSample of {sample_size} embeddings:")
            for i in range(sample_size):
                embedding_id = sample["ids"][i]
                metadata = sample["metadatas"][i] if "metadatas" in sample else {}
                embedding = sample["embeddings"][i] if "embeddings" in sample else []

                # Print summary of the embedding
                embedding_length = len(embedding) if embedding else 0
                print(f"  - ID: {embedding_id}")
                print(f"    Metadata: {metadata}")
                print(f"    Embedding: {embedding_length} dimensions")

                # Check for potential issues
                if embedding_length == 0:
                    print("    ❌ Warning: Empty embedding!")
                if not metadata:
                    print("    ⚠️ Warning: No metadata!")

        return True
    except Exception as e:
        print(f"❌ Error checking existing data: {str(e)}")
        traceback.print_exc()
        return False


def test_performance():
    """Test ChromaDB query performance."""
    print_section("ChromaDB Performance Test")

    try:
        import chromadb

        # Create in-memory client for testing
        client = chromadb.Client()
        test_collection = client.create_collection(name="perf_test_collection")

        # Number of test embeddings
        n_embeddings = 100
        print(f"Generating {n_embeddings} random embeddings for performance testing...")

        # Generate random embeddings
        embeddings = [np.random.rand(TEST_EMBEDDING_DIM).tolist() for _ in range(n_embeddings)]
        ids = [f"test_face_{i}" for i in range(n_embeddings)]
        metadatas = [{"person_id": f"person_{i % 10}"} for i in range(n_embeddings)]

        # Add embeddings
        start_time = time.time()
        test_collection.add(embeddings=embeddings, metadatas=metadatas, ids=ids)
        add_time = time.time() - start_time
        print(f"✅ Added {n_embeddings} embeddings in {add_time:.4f} seconds")

        # Test query performance
        query_embedding = np.random.rand(TEST_EMBEDDING_DIM).tolist()

        # Warm-up query
        test_collection.query(query_embeddings=[query_embedding], n_results=5)

        # Timed queries
        n_queries = 10
        total_time = 0

        print(f"Running {n_queries} test queries...")
        for i in range(n_queries):
            query_embedding = np.random.rand(TEST_EMBEDDING_DIM).tolist()
            start_time = time.time()
            test_collection.query(query_embeddings=[query_embedding], n_results=5)
            query_time = time.time() - start_time
            total_time += query_time

        avg_query_time = total_time / n_queries
        print(f"✅ Average query time: {avg_query_time:.4f} seconds")

        return True
    except Exception as e:
        print(f"❌ Error during performance test: {str(e)}")
        traceback.print_exc()
        return False


def display_environment_info():
    """Display system environment information."""
    print_section("System Environment Information")

    import platform

    print(f"Python version: {platform.python_version()}")
    print(f"Operating system: {platform.system()} {platform.release()}")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")

    try:
        import numpy

        print(f"NumPy version: {numpy.__version__}")
    except ImportError:
        print("NumPy: Not installed")

    try:
        import cv2

        print(f"OpenCV version: {cv2.__version__}")
    except ImportError:
        print("OpenCV: Not installed")

    # List other relevant packages
    try:
        import pkg_resources

        relevant_packages = ["chromadb", "onnx", "onnxruntime", "insightface"]
        print("\nRelevant package versions:")
        for package in relevant_packages:
            try:
                version = pkg_resources.get_distribution(package).version
                print(f"- {package}: {version}")
            except pkg_resources.DistributionNotFound:
                print(f"- {package}: Not installed")
    except ImportError:
        pass


def test_fix_existing_collection():
    """Test restoration of a corrupted collection (if needed)."""
    print_section("ChromaDB Collection Repair Test")

    try:
        import chromadb

        # Check if persistent directory exists
        if not CACHE_DIR.exists():
            print("⚠️ Cache directory doesn't exist, skipping repair test.")
            return True

        # Connect to the persistent database
        try:
            client = chromadb.PersistentClient(path=str(CACHE_DIR))
            collections = client.list_collections()
            collection_names = [c.name for c in collections]

            if COLLECTION_NAME not in collection_names:
                print(f"⚠️ Collection '{COLLECTION_NAME}' not found, skipping repair test.")
                return True

            # Attempt to get and use the collection
            collection = client.get_collection(COLLECTION_NAME)
            count = collection.count()
            print(
                f"✅ Collection '{COLLECTION_NAME}' appears to be functional with {count} embeddings"
            )

            # If count is 0, we might want to suggest recreation
            if count == 0:
                print("⚠️ Collection is empty, you may want to regenerate embeddings")

            return True
        except Exception as e:
            print(f"❌ Error accessing collection: {str(e)}")

            # Suggest a backup and reset approach
            print("\nSuggested repair steps:")
            print("1. Back up the current ChromaDB directory:")
            print(f"   cp -r {CACHE_DIR} {CACHE_DIR}_backup_$(date +%Y%m%d)")
            print("2. Recreate the ChromaDB collection:")
            print("   You can use fix_chromadb.py to recreate the collection")
            print("   or delete the cache directory and rerun the main program")

            return False
    except Exception as e:
        print(f"❌ Error in repair test: {str(e)}")
        traceback.print_exc()
        return False


def main():
    """Main debugging function."""
    print("\n⚙️  CHROMADB FACE RECOGNITION DEBUGGING UTILITY ⚙️\n")

    start_time = time.time()

    print(f"Project root: {PROJECT_ROOT}")
    print(f"ChromaDB cache directory: {CACHE_DIR}")

    # Run diagnostic tests
    tests = [
        ("Environment Information", display_environment_info),
        ("ChromaDB Installation", check_chromadb_installation),
        ("Database Connection", check_database_connection),
        ("Existing Data Check", check_existing_data),
        ("Embedding Operations", test_embedding_operations),
        ("Performance Test", test_performance),
        ("Collection Repair Test", test_fix_existing_collection),
    ]

    results = {}
    all_passed = True

    for name, test_fn in tests:
        print(f"\nRunning test: {name}")
        try:
            result = test_fn()
            results[name] = result
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ Unexpected error in {name}: {str(e)}")
            traceback.print_exc()
            results[name] = False
            all_passed = False

    # Print summary
    print_section("Diagnostic Summary")

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    total_time = time.time() - start_time
    print(f"\nDiagnostic completed in {total_time:.2f} seconds")

    if all_passed:
        print("\n✅ All tests passed! ChromaDB appears to be functioning correctly.")
    else:
        print("\n⚠️ Some tests failed. Review the output above for details and suggested fixes.")


if __name__ == "__main__":
    main()
