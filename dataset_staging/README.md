# MV Face Recognition Video Dataset

This dataset contains multi-quality videos for the MV Face Recognition system.

## Dataset Structure

### Video Qualities

- **480p**: Mobile-friendly, fast processing (~30MB per video)
- **720p**: Balanced quality and performance (~40MB per video)  
- **1080p**: Best quality, detailed analysis (~200MB per video)

### Contents

- `videos_480p`: 5 videos in 480p resolution (854x480)
- `videos_720p`: 5 videos in 720p resolution (1280x720)
- `videos_1080p`: 5 videos in 1080p resolution (1920x1080)
- `metadata`: Video metadata and quality information
- `embeddings`: Pre-computed face embeddings for 95+ contestants

## Usage

```python
from datasets import load_dataset

# Load 720p videos (recommended)
dataset = load_dataset("yellowcandle/mv-face-recognition-data", name="videos_720p")

# Load metadata
metadata = load_dataset("yellowcandle/mv-face-recognition-data", name="metadata")

# Load embeddings
embeddings = load_dataset("yellowcandle/mv-face-recognition-data", name="embeddings")
```

## Integration

This dataset is designed to work with the [MV Face Recognition](https://huggingface.co/spaces/yellowcandle/mv-face-recognition) Gradio application, providing scalable video storage beyond the 1GB Space limit.

## License

This dataset is provided for research and educational purposes.

## Videos

The dataset contains 5 music videos from 《全民造星IV》(King Maker IV):

1. 主題曲 《前傳》MV 2021夏の首部曲：造星の駅
2. 主題曲 《前傳》MV 2021夏の次部曲：始発の駅  
3. 主題曲 《前傳》MV 2021夏の三部曲：女團の駅
4. 極限拍MV
5. 播前熱身！率先表演《前傳》

Total duration: ~22 minutes across all videos.