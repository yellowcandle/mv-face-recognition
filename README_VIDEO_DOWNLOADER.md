# Video Downloader Usage Guide

## Overview
The `videos_dl.py` script downloads YouTube videos with proper Chinese titles for the face recognition system.

## Usage

### Basic Download
```bash
python3 videos_dl.py
```

### With Verbose Logging
```bash
python3 videos_dl.py --verbose
```

### Set Log Level
```bash
python3 videos_dl.py --log-level DEBUG
```

## Fixing Dependencies

If you encounter the fsspec warning or other dependency issues:

```bash
python3 fix_dependencies.py
```

## Video Configuration

Videos are configured in `videos_dl.py`:

```python
url_list = {
    "《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅": "https://youtu.be/IpuMy0PcPAE",
    "《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅": "https://youtu.be/2thpVqZsKHA", 
    "《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅": "https://youtu.be/O8MOUs0sz4U",
    "全民造星極限拍MV": "https://youtu.be/gizlTwFUL1M",
}
```

## Integration with Gradio

The Gradio interface automatically:
- Reads video titles from `videos_dl.py`
- Displays proper Chinese titles in the dropdown
- Maps selections back to video files
- Handles both numbered files (v1.mp4) and properly named files

## Troubleshooting

### fsspec Warning
- Run `fix_dependencies.py` or manually upgrade: `pip install --upgrade fsspec`

### Logger Error
- Fixed in the current version - uses `logger.info()` instead of `logger.success()`

### Missing Videos
- v2.mp4 and v3.mp4 are Git LFS files - use `git lfs pull` to download them
- Or run `videos_dl.py` to download fresh copies with proper names