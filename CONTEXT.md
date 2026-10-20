# MV Face Recognition

Identifying which of the 96 *King Maker* contestants appears when in a set of music videos,
and publishing those results to a viewer. This glossary exists because two terms in this
project have already caused real bugs by meaning different things in different files.

## Language

### Recognition

**Reference photo**:
One image of a known contestant, used as identification material. Lives in
`source/photo/contestants/ig_photos/contestant_{id}/`.
_Avoid_: contestant photo, training image

**Reference embedding**:
The 512-dimensional vector for the face found in **one** reference photo. There is one per
photo, not one per contestant.
_Avoid_: embedding (unqualified), encoding

**Reference set**:
All of a contestant's reference embeddings, taken together. A contestant is identified by
their whole reference set, never by a single averaged vector.
_Avoid_: centroid, average embedding, contestant embedding

**Match score**:
The cosine similarity between a detected face and a reference embedding, always in the range
−1 to 1, where **higher means more similar**. A contestant's match score is the *maximum*
across their reference set. Stored and served as `match_score` — the raw cosine, never
rescaled.
_Avoid_: distance, similarity, confidence, `match_confidence` — that field held
`1 − (distance / acceptance threshold)`, which moved whenever the threshold moved, so the same
face scored differently between runs and no stored value was comparable to another.

**Detection score**:
The detector's own confidence that a region *is a face* — InsightFace's `det_score`. It says
nothing about **whose** face it is. Stored as `det_score`, and it is the only score an
unmatched **detection** carries.
_Avoid_: confidence, min_confidence — that name has meant a detection score, a match score and
a filter threshold in three different files at once.

**Band**:
The coarse quality label shown for a **recognition** — derived from **match score** against
cutoffs set by measured false-match rate, not by dividing up an observed distribution. Bands
are provisional until ground-truth labels exist.
_Avoid_: showing a match score as a percentage — 0.64 rendered as "64%" reads as *64% certain*,
which it is not.

**Acceptance threshold**:
The lowest match score that counts as a recognition. Expressed as a cosine, in the same
direction as **match score**, so a higher threshold is stricter.
_Avoid_: tolerance — it names a *distance* (`1 − cosine`), runs in the opposite direction,
and has already been misread once as though it were a cosine.

**Detection**:
A face found in a video frame, whether or not it was identified.
_Avoid_: face, recognition

**Recognition**:
A detection that has been matched to a contestant above the acceptance threshold. Every
recognition is a detection; most detections are not recognitions.
_Avoid_: match, identification

**Flag**:
A human-proposed correction against a **detection** — an assertion of which **contestant** it
really is. A flag is a claim awaiting review, with its own pending / accepted / rejected
lifecycle; it is not a **match score** and carries no cosine. The flag record does carry the
flagged detection's match score (served as `confidence`) as context for the claim, never as the
claim's own score. Flagging is an **admin** act.
_Avoid_: correction, label, annotation, ground truth — a flag is a proposal, and only becomes
evidence once accepted.

### Data

**Contestant**:
One of the 96 people in `metadata/contestant_info.csv`, identified by their number
(編號, 1–96). Numbers are stable; nicknames are not, and several contain spaces or CJK.
_Avoid_: person, subject, participant

**Viewer**:
The public app (`apps/viewer`), served by the Cloudflare Worker. It is **read-only**: it
displays **recognitions** and never writes. Anything it can do, an anonymous stranger can do.
_Avoid_: frontend, the app, the dashboard

**Admin**:
The local-only app (`apps/admin`), served by Vite against `local_api.py` on localhost. Every
operation that writes — **flagging**, reprocessing, the embedding workbench — lives here and
is never deployed.
_Avoid_: dashboard, backend, the tool

### Geometry

**Frame fraction**:
The unit every stored face box is expressed in: a proportion of the frame's width or height,
in the range 0–1. Independent of resolution, so the same box is correct against the source,
the 1080p rendition and the 720p rendition alike.
_Avoid_: normalised coordinate, relative coordinate, percentage

**Bounding box**:
The rectangle around one **detection**, written `[x1, y1, x2, y2]` in **frame fractions** —
left, top, right, bottom, in that order. Stored in metadata as `bbox`.
_Avoid_: face_location, bbox in pixels, `[top, right, bottom, left]` — that ordering came from
the `face_recognition` library, which this project no longer uses, and reading it as
`[x1,y1,x2,y2]` swaps every box's corners.

**Detection space**:
The resolution a frame was resized to before faces were found — 1920 wide, height set by the
source's aspect ratio. It is an *internal* stage: nothing outside the pipeline should know it,
because a **bounding box** leaves the pipeline already converted to **frame fractions**.
_Avoid_: treating `video_info.width` as a scale factor. It is the *source* width, it differs
from every rendition served, and dividing by it is the bug this term exists to prevent.
