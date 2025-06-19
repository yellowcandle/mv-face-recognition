# 📝 Deployment Notes - Path Resolution Fix

## Issue Summary

The application was encountering "Videos directory not found" warnings when deployed on Hugging Face Spaces because:
- Project root was detected as `/home/user` instead of `/home/user/app`
- Videos were being searched at `/home/user/source/videos` (incorrect path)

## Fixes Applied

### 1. Enhanced Project Root Detection (`src/config/settings.py`)

Updated the `_get_project_root()` function to:
- Check current working directory first
- Try common HF Spaces paths (`/home/user/app`, `/app`)
- Look for `app.py` as a project root indicator
- Maintain backward compatibility for local development

### 2. Robust Video Directory Discovery (`gradio_app.py`)

Enhanced `get_available_videos()` method to:
- Try multiple alternative paths for video directories
- Check for alternative video folder names (`videos_hf_clean`, `videos_hf_optimized`)
- Auto-detect any directory containing "video" in its name
- Provide detailed logging for debugging

## Alternative Video Paths Checked

1. `{cwd}/source/videos`
2. `{cwd}/source/videos_hf_clean`
3. `{cwd}/source/videos_hf_optimized`
4. `/home/user/app/source/videos`
5. `/home/user/app/source/videos_hf_clean`
6. `/app/source/videos`
7. `{script_dir}/source/videos`
8. `{script_dir.parent}/source/videos`

## Debugging Information

The application now logs:
- Current working directory
- Detected project root
- Script file location
- All paths checked for videos
- Final video directory used

## Testing

To test path resolution locally:
```bash
python test_path_resolution.py
```

## Deployment Checklist

- [x] Path resolution works in local environment
- [x] Multiple fallback paths for HF Spaces
- [x] Detailed logging for debugging
- [x] Backward compatibility maintained
- [ ] Verify on actual HF Spaces deployment

## Notes

- The linter warnings about import paths are cosmetic and don't affect runtime
- The system will automatically find videos in any of the alternative locations
- If videos are still not found, check the logs for the exact paths being searched 