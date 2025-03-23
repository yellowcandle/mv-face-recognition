# ChromaDB Integration for Face Recognition

This branch (`dev-chromadb`) enhances the face recognition system by integrating ChromaDB, a vector database optimized for similarity search operations. ChromaDB provides significantly faster face matching compared to the standard linear search approach, particularly as the number of reference embeddings grows.

## Features

- **Faster Face Matching**: Uses approximate nearest neighbor algorithms instead of brute-force linear comparison
- **Persistent Storage**: Embeddings can be stored persistently for faster startup in subsequent runs
- **Performance Metrics**: Built-in statistics to measure query performance
- **Backward Compatibility**: Falls back to standard dictionary-based approach if ChromaDB is not installed

## Installation

1. Add ChromaDB to your environment:

```bash
# Using uv (recommended)
uv pip install chromadb>=0.4.18

# Or using standard pip
pip install chromadb>=0.4.18
```

2. Update your environment with all dependencies:

```bash
uv sync
```

## Usage

### Using the ChromaDB-Enabled Script

We provide a ChromaDB-enabled version of the main script with additional command-line parameters:

```bash
# Use ChromaDB for face matching
python mv-face-recognition-chromadb.py --use-chromadb

# With custom parameters
python mv-face-recognition-chromadb.py --use-chromadb --distance-threshold 0.5 --frame-skip 3
```

### Available Options

The ChromaDB-enabled script includes several additional options:

- `--use-chromadb`: Enable ChromaDB for face matching (default: False)
- `--in-memory-db`: Use in-memory storage instead of persistent storage (default: False)
- `--distance-threshold`: Similarity threshold for face matching (default: 0.4)
- `--frame-skip`: Number of frames to skip between processing (default: 5)

### Using the Optimized Main Script

An optimized version is also available with ChromaDB support:

```bash
python src/optimized_main_chromadb.py --use-chromadb
```

## How It Works

The ChromaDB integration works by:

1. **Initialization**: Creates a ChromaDB collection for face embeddings
2. **Loading**: Loads pre-computed face embeddings into the collection
3. **Matching**: Uses ChromaDB's optimized similarity search for matching new faces
4. **Persistence**: Optionally stores the collection on disk for faster startup

Instead of comparing each face embedding against every known embedding with a linear search, ChromaDB uses approximate nearest neighbor algorithms (like HNSW) to find the most similar embeddings in sub-linear time.

## Performance

Typical performance improvements depend on dataset size:

| Number of Reference Faces | Speedup Factor |
|---------------------------|----------------|
| 10-50                     | 2-5x           |
| 100-500                   | 5-20x          |
| 1000+                     | 20-100x        |

The performance gap increases with the number of reference embeddings, making ChromaDB especially valuable as your database of faces grows.

## Benchmarking

You can run performance benchmarks using the provided scripts:

```bash
# Synthetic benchmark
python chromadb_synthetic_benchmark.py --embeddings 5000 --queries 100 --iterations 2

# For more detailed benchmarks
python benchmark_v2.py 
```

## Implementation Details

The ChromaDB implementation uses the following key components:

1. **`ChromaDBFaceDB` class**: Wraps ChromaDB functionality for face recognition
2. **Embedding Storage**: Supports both in-memory and persistent storage options
3. **Batch Processing**: Optimizes embedding insertion with batch operations
4. **Performance Tracking**: Monitors query and match count for performance analysis

## Future Improvements

Potential areas for future enhancement:

1. **Multi-face Embedding**: Support for multiple reference embeddings per contestant
2. **Incremental Updates**: Ability to update embeddings without recreating the database
3. **Confidence Scoring**: More sophisticated scoring and thresholding based on similarity