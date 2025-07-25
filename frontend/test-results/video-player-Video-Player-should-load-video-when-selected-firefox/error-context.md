# Page snapshot

```yaml
- text: Loading MV Face Recognition...
- banner:
  - heading "🎬 MV Face Recognition" [level=1]
  - navigation:
    - link "🏠 Home":
      - /url: /
    - link "▶️ Video Player":
      - /url: /video-player
    - link "⚙️ Settings":
      - /url: /settings
  - text: offline
- main:
  - main:
    - heading "視頻播放器與人臉識別" [level=1]
    - button "Toggle face gallery":
      - img
      - text: 人臉識別
    - button "Switch gallery position":
      - img
      - text: 底部
    - text: ● 線上 載入中...
    - alert:
      - img
      - heading "發生錯誤" [level=3]
      - paragraph: Failed to load contestants
      - button "重新載入視頻": 重試 (3 次剩餘)
- contentinfo:
  - paragraph: © 2024 MV Face Recognition. Powered by SvelteKit & Cloudflare Workers.
```