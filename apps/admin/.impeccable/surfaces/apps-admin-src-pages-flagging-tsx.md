---
version: 1
slug: "apps-admin-src-pages-flagging-tsx"
primary_target: "apps/admin/src/pages/Flagging.tsx"
related_targets: []
---

# Surface brief — Admin (apps/admin)

Scope: the local-only back office (`apps/admin`): dashboard, player, contestants, flagging, labelling, processing, embeddings. Visitor mode: **Operate** — the operator completes a task; scanability, density and keyboard speed outrank expression, and the world lives in precise details rather than in theatre.

Audience and job: the single operator, sitting at the machine that runs `local_api.py` on localhost. Job: clear the flag queue honestly — accept a human-proposed correction, void it, or reassign it to the right contestant — and see the health of the pipeline. Action: 蓋印確認 (accept) on the selected slip. Frequency: high, hundreds per session, so keyboard shortcuts are part of the design, not a bonus.

Constraints: every write lives here and here only; admin is never deployed. It shares one world with the viewer, but takes the 存根 (office copy) role: the writable retained stub of the same form. Raw cosines stay raw; bands are provisional stamps.

## Direction contract

THESIS: The back office is the 存根 — the office copy of the same request slip, the one that may be written on. A filing desk, not an admin dashboard.

OWN-WORLD: Same materials as the viewer, one step dirtier: `#EDE3B6` ground, `#FAF3D7` selected slip, carbon ink, stamp red for voided and for the primary action, ledger grey. Struck stamps for every state, 1px carbon rules, 3px red edge marking the selected row. No cards, no icons-as-buttons, no colour-coded pills.

STORY: The operator reads the queue top-down, opens a slip, compares the crop against the nearest references and five context frames, then stamps it. Every state is a mark on paper: 待核 / 已核對 / 作廢 / 需重算.

FIRST VIEWPORT (1440×900): Same 76px punched spine, folio `NO. 02`. Masthead 存根 at 44px with `OFFICE COPY · WRITABLE`, a `LOCAL API ONLINE` lamp, a rotated 待核 12 stamp; 待核 stays as the section heading above the tray. A counters rule counted from the flag records themselves (待核 / 已核對 / 作廢 / 全部). EMBEDDINGS STALE was dropped because no endpoint reports it; no per-day count is shown because nothing is counted per day. Left 742px tray: seven pending slip rows — crop, timecode, video, name with 編號, band stamp, the flagged detection's match score, 蓋印/作廢 stamps. Right: the review sheet — 186×210 crop with DET (looked up in dense metadata by exact bbox in the floor frame; shown as unavailable when there is no match, since the flag record carries no det_score), currently filed as 阿杰 #47 with the detection's match-score bar marked at the 0.45 acceptance threshold (the flag itself carries no score), three reference slots (only one is real: `/api/contestants/{id}/photo` serves one photo, unranked, so the other two are marked 未提供 and none is claimed "nearest"), reassign picker, a five-frame context strip (the processed frames either side of the floor frame, from dense metadata, rendered from the stream; empty slots say so), note line with the 1/2/3/↓ keys (live: 1 accept, 2 void, 3 focus reassign, ↓ next; silent in fields and under a modal), and the 蓋印確認 bar.

FORM: same world as the viewer, derived from roll candidate 7. seed:d67e9ffa10bdad6e.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
