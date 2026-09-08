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
across their reference set.
_Avoid_: distance, similarity, confidence

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

### Data

**Contestant**:
One of the 96 people in `metadata/contestant_info.csv`, identified by their number
(編號, 1–96). Numbers are stable; nicknames are not, and several contain spaces or CJK.
_Avoid_: person, subject, participant
