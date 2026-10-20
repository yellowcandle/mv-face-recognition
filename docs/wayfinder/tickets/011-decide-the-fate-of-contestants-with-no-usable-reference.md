---
id: 011
title: Decide the fate of contestants with no usable reference
label: wayfinder:grilling
mode: HITL
blocked_by: []
status: closed
assignee:
---

## Question

13 of the 96 contestants have **no reference photo that yields a face**. They cannot be
recognised under any matching strategy. What happens to them?

- **(a)** Accept it. They are permanently unrecognisable; the analytics silently omit them.
- **(b)** Source replacement photos for those 13 (manual, and the user is the only one who
  can pick them).
- **(c)** Keep them recognisable-in-principle but mark them explicitly, so the viewer can say
  "no reference on file" rather than "not in this video".

## Context

Surfaced by *Measure within-person embedding separation*, which corrects the assumption in
*Choose the reference-embedding storage shape* that `ig_photos/` gains references for 12
contestants who currently have none.

- The 13: 8 小砂, 13 Ashi, 23 陳祖, 36 精靈, 45 Jade Chan, 53 丁丁, 54 Miko, 58 Kinki,
  61 燒賣, 66 Sam, 67 Sarah, 69 鉦貽, 86 Michelle. **Their `ig_photos/contestant_{id}/`
  directories are completely empty** — this is not detection failure, the download never ran
  for them. (Corrects an earlier claim in this ticket that buffalo_l was run over their files;
  there were no files.) All 13 *do* have an Instagram handle in `metadata/contestant_info.csv`,
  which has an `instagram` column populated for all 96.
- **The photos are not merely undownloaded — they are unrecoverable from every source in the
  repo.** `source/photo/contestants/photos/` has entries for **12 of the 13** (all but 13/Ashi)
  across 84 contestant dirs, but all 160 files are 131-byte Git-LFS pointer text. Verified
  2026-09-08 that the real bytes exist nowhere reachable:
  - `git lfs pull` fetches nothing — the objects are not on the GitHub remote.
  - The HuggingFace dataset `yellowcandle/mv-face-recognition-data` stores **the same pointer
    text**: its `photos/` prefix is 160 files totalling **0.02 MB**. This contradicts
    `CLAUDE.md`, which claims 196 photos / 3.97 MB migrated. `embeddings/` there is real but
    useless for this — 338 files, every one exactly 2176 bytes, i.e. all single `(512,)`
    centroids under the old one-vector-per-contestant convention.
  - Branch `backup-before-hf-migration` has nothing at that path, and no blob for those files
    exists anywhere in git history.
  - The only real image bytes under `source/photo/` are in `ig_photos/`.
- **Anonymous Instagram fetching is dead**, so re-downloading is not a fallback: the profile
  HTML is a 620 KB JS shell with no `og:image` and no CDN URLs; `web_profile_info` returns
  `require_login: true`; `yt-dlp` fails to extract; headless `browse` renders "Profile isn't
  available / Log in". All 96 handles are in `metadata/contestant_info.csv`; the 13 are
  waacker.siusa, bikkuri.ashi, jo2_ig, 0.sakiikas.0, jadechansnowflake, tingting_fong, ykw.ko,
  kinki_is_here, siumaiii_0426, samantha.lwh, sarah_yangtszching, zoewcyyy, _lmhmc.
- **User's position (2026-09-08)**: option (c), supply photos by hand rather than scrape —
  believing the photos were already on disk. They are not, in this repo. If a copy exists
  outside it, dropping files into the empty `ig_photos/contestant_{id}/` dirs is the whole fix.

### 13/Ashi is RESOLVED (2026-09-08) — 12 remain

Contestant 13 (曾善婷 / Ashi) was the worst case: the only one of the 13 with no entry even in
the pointer-only `photos/` tree. Now fixed. `ig_photos/contestant_13/` holds
`13_ig_1.jpg` … `13_ig_5.jpg`, sourced from a public gallery of her ViuTV and Instagram
material at <https://jdailyhk.com/2021/11/bikkuri-ashi/>.

Vetted before placement, and this is the bar any further sourcing should clear:

1. **All 5 are single-face**, so they survive the curation rule from *Choose the matching
   strategy*. A sixth image was a 5-person group shot and was discarded, not stored.
2. **They are internally consistent**: within-person cosine mean 0.610, min 0.546, max 0.686 —
   far above this project's measured within-person mean of 0.318. They are one person.
3. **They are not a duplicate of anyone already in the set.** Scored against all 672 existing
   reference embeddings, the best match to *any* of the 83 contestants was 0.312, below the
   0.45 acceptance threshold. Contestant 81 (Ash / 鍾卓穎), the name-alike most likely to be
   confused with her, scored 0.176.
4. **Identity confirmed visually**: one image is an official ViuTV 全民造星IV promotional card
   with "13 Ashi" printed on it.

Her handle `bikkuri.ashi` in `metadata/contestant_info.csv` is confirmed correct by an
independent source.

### 2026-09-08 (later): 12 of 13 resolved. Only 67/Sarah remains.

`ig_photos/` went from 741 photos to **964**; exactly one contestant now has none.

**Where the photos came from, and why jdailyhk was mostly a dead end.** Its posts are indexed
by IG handle (`sitemap.xml` → `sitemap-pt-post-2021-11.xml`), which matched 91 of 96
contestants; the 5 misses had renamed their accounts (contestant 8 is at `siusaaaa`, not the
`waacker.siusa` in the CSV). But **only 19 galleries still have live images** — contestants 1
and 10–27. Everything from 28 up returns 404, verified not to be rate-limiting: a known-good
URL kept returning 200 throughout, and no filename variant or upload month resolves. So that
source could not reach 10 of the 13.

**The route that worked: the show's own solo footage.** Each contestant has a
《全民造星IV》Pre round比賽 clip on YouTube featuring only them, and ViuTV burns a lower-third
into the frame reading the contestant's **number and nickname** — so every extracted frame
self-identifies, which is stronger evidence than any gallery page title. Sampled a frame every
1.5 s, kept single-face frames with `det_score ≥ 0.7` and a face at least 80 px wide, took the
medoid cluster, and spread the picks across the clip.

`yt-dlp` 2025.06.09 could not read YouTube's current playlist layout (it reported
"Downloading 0 items of 23"). Updated to 2026.08.19 in the user's Python environment; this was
required, not optional.

**Multi-person clips are usable when the other people are already known.** For 67/Sarah, only
interview footage existed. Clustering the faces and scoring each cluster against the existing
reference set identified a 207-frame cluster as contestant 7 and a 171-frame cluster as
contestant 2 (咖喱) — leaving the remainder as Sarah by elimination. Worth reusing.

**67/Sarah is deliberately left empty.** Her surviving footage is Instagram Live
split-screens: two or three people tiled in one frame, plus other users' profile thumbnails.
They pass a naive single-face filter only because the detector happens to find one face per
frame, and `faces[0]` could later pick the wrong tile. Given this map's finding that a wrong
reference is worse than none, they were discarded rather than placed. She needs a genuine solo
clip or a hand-supplied photo.

**Also enriched, not just repaired**: 130 vetted gallery photos were added across 16
contestants who already had references. Each set was accepted only because it matched **that
contestant's own** existing references as its top hit (0.506–0.746, all above the 0.45
acceptance threshold) — which independently confirms both the new photos and the existing ones.

⚠️ **`docs/wayfinder/assets/photo_embeddings.npz` is now stale.** It was built from the old 741
photos. Regenerate with `extract_photo_embeddings.py` before any further measurement.
- Contestant 77 is a separate, milder case: exactly one usable photo, so no within-person
  spread at all.
- **The set grew to 14.** *Choose the matching strategy* settled on dropping multi-face photos,
  which costs one further contestant their last reference (83 → 82 with any reference at all).
- This is the difference between "absent from this MV" and "unrecognisable anywhere", and
  the per-contestant screen-time analytics in the map's Destination cannot distinguish them
  today. That is the real cost of (a).
- `has_embedding` (`apps/shared/types/index.ts:6`) is already the field that would carry (c),
  and *Choose the reference-embedding storage shape* is redefining what it means. Fold the
  two if (c) wins.

### Was the expansion worth it? Measured 2026-09-08

Cache regenerated from the 964 photos (895 embeddings, 69 photos yield no face). Leave-one-out
rerun with the query set held fixed to the 440 clean photos present in **both** caches, so only
the reference set varies:

| | old (741) | new (964) |
|---|---|---|
| usable references after curation | 440 | 663 |
| contestants representable | 83 | **95** |
| top-1 correct | 94.0% | 94.0% |
| own score mean | 0.555 | 0.560 |
| best impostor mean | 0.293 | 0.301 |
| own accepted @0.45 | 78.7% | 79.8% |
| impostor also accepted @0.45 | 1.1% | 1.1% |

**The expansion bought coverage, not accuracy, and cost nothing.** Top-1 is unchanged because
the fixed query set contains only photos of contestants who *already* had references — the 12
who gained references contribute no queries, so their move from unrecognisable to recognisable
cannot appear in this number. Best-impostor mean drifting up 0.008 is the expected price of
more references; false accepts at the threshold did not move.

Do **not** read 94.0% as "the recogniser is 94% accurate on video". These are reference photos
matched against reference photos. The real figure still needs *Label 30 seconds of
test-video-mv2*.
