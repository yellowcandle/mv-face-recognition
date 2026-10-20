---
version: 1
slug: "apps-viewer-src-pages-playerpage-tsx"
primary_target: "apps/viewer/src/pages/PlayerPage.tsx"
related_targets: []
---

# Surface brief — Viewer (apps/viewer)

Scope: the public read-only viewer (`apps/viewer`), all three routes: library (`/`), player (`/player`), analytics (`/analytics`). Visitor mode: **Experience** — the artifact (the MV and its faces) leads from the first viewport. No writes anywhere on this surface.

Audience and job: a fan who wants to know which of the 96 全民造星 contestants is on screen at this second, and who appears next. Action: press play, then read the tray. Content is real: 5 processed videos, 96 contestants, dense per-frame recognitions, raw cosine match scores.

Constraints: viewer is public and read-only (anything it can do, an anonymous stranger can do); recognition data only — no invented claims, no percentages presented as certainty; Traditional Chinese primary with English small caps; contestant numbers (編號) are the stable identifier; band names are provisional.

## Direction contract

THESIS: Every appearance is a dedication slip filed at its timestamp. The surface is a carbonless request form, not a video dashboard — it refuses the poster-grid-and-cards arrangement the category ships.

OWN-WORLD: Canary NCR paper `#F2E8BC` ground, pale blue carbon copy `#C6DAE9` for the second sheet, carbon ink `#2B2F6B`/`#1F2455`, rubber-stamp red `#AE3B2C`, ledger grey `#8A857A`. Noto Serif TC 900 sets printed form headings; LXGW WenKai TC 700 is the handwriting in every filled field and every name; JetBrains Mono carries timecodes, counts and cosines. No rounded corners, no shadows, no pills; 1px carbon rules, punched holes, rotated stamps.

STORY: The fan sees the video as a slide clipped to a form, reads who is on screen right now in the tray under it, and sees who is coming in the queue. A band is a stamp (清楚 / 尚可 / 存疑), never a percentage. The viewer is marked 唯讀 — reads never write.

FIRST VIEWPORT (1440×900): 76px punched spine with folio `NO. 01` at left. Masthead: 點唱單 at 46px Noto Serif TC 900, `REQUEST SLIP` beside it, a rotated 已核對 stamp at right. One 1px rule, then a filled-fields row (節目 / 影片 / 時段 / 在場). The 16:9 video at 950×534 holds the frame with canary face boxes and slip-shaped name tags, play control bottom-left. Under it the 現在 tray: three filed slips in one row. Right 330px: the 第二聯 copy in blue, headed 待播, six queue rows, a 唯讀 stamp, and coverage `7 / 96`.

FORM: replacement world; roll candidate 7 of 7 (the last, least-obvious of the grounded list). seed:d67e9ffa10bdad6e.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
