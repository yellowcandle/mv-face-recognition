# 全民造星IV MV 人臉識別

本項目旨在對ViuTV的全民造星IV選秀節目影片進行人臉識別分析。我們使用先進的人工智能技術，自動識別和追蹤影片中出現的參賽者。

## Problem Definition

如果你有聽過[Lolly Talk嘅三分甜](https://youtu.be/cTtBqzGI-HM)嘅話，你會發覺入邊有一句歌詞係

> 狂奔過東壩的你  

咁所以我哋嘅問題就係：既然 Lolly Talk 嘅成員大部份都係造星 IV 嘅第二個 MV 入邊出現過，咁樣我哋可唔可以用 AI 去認返究竟邊幾個參賽者有去喺東壩度跑步呢？
咁 generalize 咗個問題之後呢，我哋就可以用AI去嘗試回答呢個問題啦。

Note: 全民造星 IV 嘅 MV 總共 3 首，分別係：  
1. [《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅](https://youtu.be/IpuMy0PcPAE)  
2. [《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅](https://youtu.be/2thpVqZsKHA)  
3. [《全民造星IV》主題曲《前傳》MV 2021夏の三部曲：女團の駅](https://youtu.be/O8MOUs0sz4U)  

撈埋電視汁系列：
- [全民造星極限拍MV](https://youtu.be/gizlTwFUL1M)
- [Lolly Talk 三分甜 MV](https://youtu.be/cTtBqzGI-HM) (呢條我哋當 bonus track run 埋佢，因為入面有好多造星 IV 嘅 cameo)

## Rationale

喺造星 IV 總共有 96 位參賽者，咁你用肉眼睇可能都要 rewind 好多次先睇到有邊幾個係有出現過喺 MV 入面。
所以其實我哋可以透過 AI 去搵出嚟究竟邊幾個參賽者有出現過喺 MV 入面。
而且人嘅記憶力有限，加上本人面盲，所以都係用電腦好啲⋯⋯

## 答返個問題先

返返正題先，「狂奔過東壩的你」係第二個 MV 入面出現嘅片段嚟。
喺 MV 入面嘅 00:48-00:55，02:10-02:13，02:39-02:40 同埋 02:49
都有剪輯到相關嘅片段，
所以我哋就可以集中處理呢幾個片段入面嘅參賽者啦。

（其真係比我哋想像中要少嘅片段）

但係喺條 BTS 入面我哋亦會搵到相關嘅片段，我哋會一併處理呢啲片段。

### Shot 1 (00:50-00:55)

首先係第一個出現嘅 shot，喺大約 MV 嘅 48 秒，即係入「想戰鬥 即戰鬥」果句果個 shot。一開始係只影到腳，所以未有人樣出現；但去到 50 秒嘅時候，我哋就終於見到「狂奔過東壩的第一批女仔」喇。  
![sample1](./samples/frame_1260_2s.jpg)
![sample2](./samples/frame_1275_2s.jpg)
![sample3](./samples/frame_1280_2s.jpg)
![sample4](./samples/frame_1290_2s.jpg)
![sample5](./samples/frame_1300_2s.jpg)  

有趣嘅係，同一個 shot 應該有喺 BTS 度出現過

![sample](./samples/frame_2380_4s.jpg)  

少少補充，唔知點解 Sinnie 只有喺 BTS 嘅大頭 shot 度出現，反而喺 MV 本身度係 detect 唔到佢，唔知點解。

<!-- ### Shot 2 (02:10-02:13) -->



## Project Aims

1. To implement a modern AI / deep learning-based face recognition pipeline to identify contestants in MV videos of *King Maker IV*, a reality show from the Hong Kong-based TV station, ViuTV.
2. To build a comprehensive database of contestants' photos and information.
3. To automatically detect and label contestants in the MV videos.

## Output Catalogue
所有參賽者喺MV同埋BTS出現過，然後認到嘅畫面呢已經喺**[呢個catalogue](catalogue.md)**入邊㗎啦。

## Challenges

其實可以分為技術層面嘅難度，同埋 data preprocessing 同埋 cleaning 嘅難度

### data preprocessing & cleaning
咁嗰個難度喺邊度呢？最主要係第一要蒐集到全部96位參賽者嘅相片啦，另外就係要去用現代嘅AI去做佢哋嘅面容嘅辨識啦。
其實成個嘅動作唔困難嘅，第一個部份嘅相片其實可以喺ViuTV嘅Facebook album入邊搵到嘅。不過問題係因為Facebook嘅 user interface 係刻意寫到你好難去做呢啲 scraping， 咁所以最後呢要將成個嘅HTML File掹咗落嚟再喺入邊掹返晒所有static嘅相link嘅。
咁相關嘅相 link 呢就已經喺以下呢一個嘅Path入面啦。
source/photo/raw/album1_image_urls.txt
source/photo/raw/album2_image_urls.txt

### tech stack and pipeline

困難喺macOS同埋Windows set up嗰個python environment。
因為唔知乜嘢緣故呢，insightface喺macOS度用 ```pip install``` 係會出事嘅，所以最後都係要用 ```--no-binary``` 去直接 build 嘅。

## Project Setup and Installation

Refer to [project main page](https://github.com/yellowcandle/mv-face-recognition) for details.

## Technical Details

TBC

## Raw Output images

[output_frames](https://github.com/yellowcandle/mv-face-recognition/tree/main/output_frames)

