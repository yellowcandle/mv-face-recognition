# 香港全民造星IV人臉識別項目

本項目旨在對ViuTV的全民造星IV選秀節目影片進行人臉識別分析。我們使用先進的人工智能技術，自動識別和追蹤影片中出現的參賽者。

## Problem Definition

如果你有聽過Lolly Talk嘅三分甜嘅話，你會發覺入邊有一句歌詞係

> 狂奔過東壩的你  

咁所以我哋嘅問題就係既然 Lolly Talk 嘅成員大部份都係造星 IV 嘅第二個 MV 入邊出現過，咁樣我哋可唔可以用 AI 去認返究竟邊幾個參賽者有去喺東壩度跑步呢？
咁 generalize 咗呢一個嘅問題之後呢，我哋就可以用AI去嘗試回答呢個問題。

## Challenges

咁嗰個難度喺邊度呢？最主要係第一要蒐集到全部96位參賽者嘅相片啦，另外就係要去用現代嘅AI去做佢哋嘅面容嘅辨識啦。
其實成個嘅動作唔困難嘅，第一個部份嘅相片其實可以喺ViuTV嘅Facebook album入邊搵到嘅。不過問題係因為Facebook嘅 user interface 係刻意寫到你好難去做呢啲 scraping， 咁所以最後呢要將成個嘅HTML File掹咗落嚟再喺入邊掹返晒所有static嘅相link嘅。
咁相關嘅相 link 呢就已經喺以下呢一個嘅Path入面啦。
source/photo/raw/album1_image_urls.txt
source/photo/raw/album2_image_urls.txt

困難喺macOS同埋Windows set up嗰個python environment。
因為唔知乜嘢緣故呢，insightface喺macOS度用 ```pip install``` 係會出事嘅，所以最後都係要用 ```--no-binary``` 去直接 build 嘅。

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

## Output images

[output_frames](https://github.com/yellowcandle/mv-face-recognition/tree/main/output_frames)

