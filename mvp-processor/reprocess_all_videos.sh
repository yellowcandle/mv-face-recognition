#!/bin/bash

# Reprocess all videos with improved overlay synchronization and Apple Silicon acceleration
cd /Users/yellowcandle/dev/mv-face-recognition/mvp-processor

echo "Starting reprocessing of all 5 videos with improved pipeline..."
echo "Date: $(date)"

# Process video-1
echo "================================"
echo "Processing video-1..."
echo "================================"
python src/process_video.py -i "../source/videos/1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4" -o "video-1" --no-upload
if [ $? -eq 0 ]; then
    echo "✅ video-1 completed successfully"
else
    echo "❌ video-1 failed"
fi

# Process video-2
echo "================================"
echo "Processing video-2..."
echo "================================"
python src/process_video.py -i "../source/videos/2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4" -o "video-2" --no-upload
if [ $? -eq 0 ]; then
    echo "✅ video-2 completed successfully"
else
    echo "❌ video-2 failed"
fi

# Process video-3
echo "================================"
echo "Processing video-3..."
echo "================================"
python src/process_video.py -i "../source/videos/3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4" -o "video-3" --no-upload
if [ $? -eq 0 ]; then
    echo "✅ video-3 completed successfully"
else
    echo "❌ video-3 failed"
fi

# Process video-4
echo "================================"
echo "Processing video-4..."
echo "================================"
python src/process_video.py -i "../source/videos/4-《全民造星IV》極限拍MV.mp4" -o "video-4" --no-upload
if [ $? -eq 0 ]; then
    echo "✅ video-4 completed successfully"
else
    echo "❌ video-4 failed"
fi

# Process video-5
echo "================================"
echo "Processing video-5..."
echo "================================"
python src/process_video.py -i "../source/videos/5-《全民造星IV》播前熱身！率先表演《前傳》.mp4" -o "video-5" --no-upload
if [ $? -eq 0 ]; then
    echo "✅ video-5 completed successfully"
else
    echo "❌ video-5 failed"
fi

echo "================================"
echo "Reprocessing complete!"
echo "Date: $(date)"
echo "================================"