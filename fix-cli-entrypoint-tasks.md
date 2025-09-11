# Tasks: Fix CLI Entry Point Issue

**Problem**: The CLI command `mv-face-recognition` fails with `ModuleNotFoundError: No module named 'src'` because of incorrect module path in the installed entry point.

## Quick Fix Tasks

### T001 - Clean Previous Installation
- [ ] Remove any cached/incorrect installations
```bash
python -m pip uninstall mv-face-recognition -y
uv pip uninstall mv-face-recognition -y 2>/dev/null || true
rm -f /Users/yellowcandle/.pyenv/shims/mv-face-recognition
```

### T002 - Verify pyproject.toml Configuration
- [ ] Check that pyproject.toml has correct entry point
- Current: `mv-face-recognition = "src.cli.main:main"`
- Should be: `mv-face-recognition = "src.cli.main:main"`

### T003 - Reinstall Package with uv
- [ ] Install package in editable mode using uv
```bash
cd /Users/yellowcandle/dev/mv-face-recognition
uv pip install -e .
```

### T004 - Test CLI Command
- [ ] Verify the CLI works after reinstallation
```bash
mv-face-recognition --help
```

### T005 - Alternative: Direct Python Module Execution
- [ ] If installation fails, use direct module execution as workaround
```bash
python -m src.cli.main --help
```

## Root Cause
The issue appears to be a mismatch between:
1. What pyproject.toml specifies: `src.cli.main:main`
2. What gets installed: Looking for `src.mv_face_recognition.launch:main`

This suggests either:
- A previous installation with different configuration
- Cached build artifacts
- Conflicting installations between pip and uv

## Permanent Solution
If the quick fix doesn't work, we need to:
1. Check for any build artifacts in the project
2. Clear all Python caches
3. Ensure clean installation environment