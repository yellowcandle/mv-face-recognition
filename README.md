# 全民造星IV MV 人臉識別

本項目旨在對ViuTV的全民造星IV選秀節目影片進行人臉識別分析。我們使用先進的人工智能技術，自動識別和追蹤影片中出現的參賽者。

## 主要功能

1. **影片下載**: 使用 `yt-dlp` 從 YouTube 自動下載指定的全民造星IV MV 影片。

2. **人臉識別**: 運用 InsightFace 深度學習模型，對影片中的人臉進行識別。

3. **參賽者資料庫**: 建立並維護一個包含全民造星IV參賽者照片和個人資訊的資料庫。

4. **自動標記**: 在影片幀上自動標記識別出的參賽者，包括姓名和出現時間。

5. **結果分析**: 生成詳細報告，顯示每位全民造星IV參賽者在影片中的出現頻率和時間點。

## 技術細節

- 使用 Python 作為主要編程語言
- 採用 OpenCV 進行影像處理
- 利用 InsightFace 進行高精度人臉識別
- 應用 Pandas 進行數據分析和報告生成

## 使用方法

1. Use `uv` to prepare the environment

https://github.com/astral-sh/uv

```bash
uv venv
```

2. Install dependencies

```bash
uv sync
```
Note: you may need to install insightface manually

```bash
pip install insightface
```
use the following command to install insightface on macos if it fails to build

```bash
pip install insightface --only-binary :all:
```
same for opencv

```bash
pip install opencv-python --only-binary :all:
```

3. Run the script

```bash
python mv-face-recognition.py
```
