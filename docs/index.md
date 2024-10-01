# 全民造星IV MV 人臉識別

本項目旨在對ViuTV的全民造星IV選秀節目影片進行人臉識別分析。我們使用先進的人工智能技術，自動識別和追蹤影片中出現的參賽者。

## Problem Definition

如果你有聽過[Lolly Talk嘅三分甜](https://youtu.be/cTtBqzGI-HM?si=LGG1-lxP52m3lNPI)嘅話，你會發覺入邊有一句歌詞係

> 狂奔過東壩的你  

咁所以我哋嘅問題就係既然 Lolly Talk 嘅成員大部份都係造星 IV 嘅第二個 MV 入邊出現過，咁樣我哋可唔可以用 AI 去認返究竟邊幾個參賽者有去喺東壩度跑步呢？
咁 generalize 咗呢一個嘅問題之後呢，我哋就可以用AI去嘗試回答呢個問題。

Note: 全民造星 IV 嘅 MV 總共 3 首，分別係：  
1. [《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅](https://youtu.be/IpuMy0PcPAE?si=54EeV1wjap1IkEeW)  
2. [《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅](https://youtu.be/2thpVqZsKHA?si=Vam2rSjE8sGh2cde)  
3. [《全民造星IV》主題曲《前傳》MV 2021夏の三部曲：女團の駅](https://youtu.be/O8MOUs0sz4U?si=nzdA3CcE10TKcykb)  



## Project Aims

1. To implement a modern AI-based face recognition pipeline to identify contestants in MV videos.
2. To build a comprehensive database of contestants' photos and information.
3. To automatically label contestants in MV videos.

## Challenges

咁嗰個難度喺邊度呢？最主要係第一要蒐集到全部96位參賽者嘅相片啦，另外就係要去用現代嘅AI去做佢哋嘅面容嘅辨識啦。
其實成個嘅動作唔困難嘅，第一個部份嘅相片其實可以喺ViuTV嘅Facebook album入邊搵到嘅。不過問題係因為Facebook嘅 user interface 係刻意寫到你好難去做呢啲 scraping， 咁所以最後呢要將成個嘅HTML File掹咗落嚟再喺入邊掹返晒所有static嘅相link嘅。
咁相關嘅相 link 呢就已經喺以下呢一個嘅Path入面啦。
source/photo/raw/album1_image_urls.txt
source/photo/raw/album2_image_urls.txt

困難喺macOS同埋Windows set up嗰個python environment。
因為唔知乜嘢緣故呢，insightface喺macOS度用 ```pip install``` 係會出事嘅，所以最後都係要用 ```--no-binary``` 去直接 build 嘅。

## Project Setup and Installation

Refer to [project main page](https://github.com/yellowcandle/mv-face-recognition) for details.

## Technical Details


## Output images

[output_frames](https://github.com/yellowcandle/mv-face-recognition/tree/main/output_frames)

