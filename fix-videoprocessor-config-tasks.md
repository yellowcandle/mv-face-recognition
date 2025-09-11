# Tasks: Fix VideoProcessor Config Parameter Issue

**Problem**: CLI passes `config` (dict) to VideoProcessor, but VideoProcessor expects `config_path` (str)

## Root Cause Analysis
The error occurs because:
1. CLI calls: `VideoProcessor(config=config)` - passes config dictionary
2. VideoProcessor expects: `VideoProcessor(config_path="config.json")` - expects file path string

## Quick Fix Tasks

### T001 - Update VideoProcessor Constructor
- [ ] Modify VideoProcessor.__init__() to accept either config dict or config path
```python
def __init__(self, config_path: str = "config.json", config: Optional[dict] = None):
    """Initialize video processor with config dict or config file path."""
    if config is not None:
        # Use provided config dict
        self.config = config
    else:
        # Load from file path
        with open(config_path, "r") as f:
            self.config = json.load(f)
```

### T002 - Update CLI Call
- [ ] Change CLI to pass config correctly
```python
# Instead of:
processor = VideoProcessor(config=config)

# Use:
processor = VideoProcessor(config=config)  # Now works with updated constructor
```

### T003 - Test the Fix
- [ ] Test the CLI command that was failing
```bash
cd /Users/yellowcandle/dev/mv-face-recognition
source .venv/bin/activate
uv run mv-face-recognition process source/videos/test-video-mv2.mp4 -m frames
```

### T004 - Alternative: Create Temporary Config File
- [ ] If constructor change is not preferred, create temp config file
```python
import tempfile
import json

# Create temporary config file
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(config, f)
    temp_config_path = f.name

processor = VideoProcessor(config_path=temp_config_path)
```

## Implementation Details

### Current VideoProcessor Constructor
```python
def __init__(self, config_path: str = "config.json"):
    with open(config_path, "r") as f:
        self.config = json.load(f)
```

### Proposed Updated Constructor
```python
def __init__(self, config_path: str = "config.json", config: Optional[dict] = None):
    if config is not None:
        self.config = config
    else:
        with open(config_path, "r") as f:
            self.config = json.load(f)
```

### CLI Usage
```python
# Load config from file
config = load_config(config_path)

# Pass config dict to VideoProcessor
processor = VideoProcessor(config=config)
```

## Testing
After fix, test these commands:
- `uv run mv-face-recognition process video.mp4 -m frames`
- `uv run mv-face-recognition process video.mp4 -m video`
- `uv run mv-face-recognition status`

## Benefits of This Fix
1. **Backward Compatibility**: Still supports config file path
2. **Flexibility**: CLI can pass config dict directly
3. **No Breaking Changes**: Existing code continues to work
4. **Clean Interface**: Single constructor handles both use cases