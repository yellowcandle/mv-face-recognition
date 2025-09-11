# MV Face Recognition - Code Style & Conventions

## Frontend (SvelteKit/TypeScript)

### File Structure
- **Atomic Design Pattern**: atoms → molecules → organisms
- **Route-based structure**: `src/routes/` for pages
- **Component organization**: `src/lib/components/`
- **Store management**: `src/lib/stores/`

### TypeScript Standards
- **Strict TypeScript** configuration enabled
- **Type definitions** for all props and stores
- **Interface definitions** for API responses
- **Generic types** for reusable components

### Code Style
- **ESLint** with TypeScript rules
- **Prettier** for consistent formatting
- **Camel case** for variables and functions
- **Pascal case** for component names
- **Kebab case** for file names

## Python (Backend Processing)

### Code Organization
- **src/** directory structure
- **Class-based** architecture for services
- **Function-based** for utilities
- **Type hints** required for all functions
- **Docstrings** for classes and public methods

### Style Guidelines
- **PEP 8** compliance via flake8
- **Black** formatting (automated)
- **isort** for import organization
- **Type hints** using typing module
- **Snake case** for variables and functions
- **Pascal case** for classes

### Example Python Function
```python
from typing import List, Optional

def process_video_frames(
    video_path: str,
    output_dir: str,
    skip_frames: int = 1
) -> Optional[List[str]]:
    """
    Process video frames for face recognition.
    
    Args:
        video_path: Path to input video file
        output_dir: Directory for processed output
        skip_frames: Number of frames to skip between processing
        
    Returns:
        List of processed frame paths or None if failed
    """
    pass
```

## Node.js Scripts

### Structure
- **CommonJS** modules for compatibility
- **Commander.js** for CLI interfaces
- **Chalk** for colored output
- **Error handling** with proper exit codes

### Testing Standards
- **Jest** for unit testing
- **Coverage thresholds**: 75-80% minimum
- **Mock external dependencies**
- **Integration test patterns**

## API Design (Cloudflare Workers)

### RESTful Conventions
- **Resource-based URLs**: `/api/videos/{id}`
- **HTTP methods**: GET, POST, PUT, DELETE
- **JSON responses** with consistent structure
- **Error handling** with appropriate status codes

### Response Format
```javascript
{
  "success": true,
  "data": {...},
  "error": null,
  "timestamp": "2025-01-09T..."
}
```

## Database/Storage Conventions

### ChromaDB Collections
- **Embedding collections**: `contestant_embeddings`
- **Metadata storage**: Structured JSON
- **ID patterns**: `contestant_{number}_{type}`

### File Naming
- **Videos**: `{id}-{title}_annotated.mp4`
- **Metadata**: `{id}_metadata.json`
- **Thumbnails**: `{id}_thumb.jpg`
- **Embeddings**: `{contestant_id}_embedding.npy`

## Git Conventions

### Commit Messages
- **Conventional Commits** format
- **feat:** for new features
- **fix:** for bug fixes
- **docs:** for documentation
- **test:** for testing changes

### Branch Naming
- **feature/**: `feature/enhanced-bbox-visualization`
- **fix/**: `fix/chromadb-connection`
- **docs/**: `docs/update-readme`