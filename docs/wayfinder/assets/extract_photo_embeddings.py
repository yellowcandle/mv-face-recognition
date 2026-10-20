"""Ticket 001 phase A: one embedding per reference photo, production convention.

Mirrors mvp-processor/src/face_detector.py:_get_insightface_app (buffalo_l, 640x640,
CoreML->CPU) and takes faces[0] like reference extraction does. Scratch only.
"""
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

import cv2
import numpy as np

REPO = Path("/Users/yellowcandle/dev/mv-face-recognition")
PHOTOS = REPO / "source/photo/contestants/ig_photos"
OUT = Path(__file__).parent / "photo_embeddings.npz"

from insightface.app import FaceAnalysis

app = FaceAnalysis(name="buffalo_l", providers=["CoreMLExecutionProvider", "CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))

rows, cids, paths, nfaces, scores = [], [], [], [], []
skipped = []

dirs = sorted(PHOTOS.glob("contestant_*"), key=lambda p: int(p.name.split("_")[1]))
for d in dirs:
    cid = d.name.split("_")[1]
    files = sorted(f for f in d.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png"})
    for f in files:
        img = cv2.imread(str(f))
        if img is None:
            skipped.append((str(f.relative_to(PHOTOS)), "unreadable"))
            continue
        faces = app.get(img)
        if not faces:
            skipped.append((str(f.relative_to(PHOTOS)), "no_face"))
            continue
        face = faces[0]  # highest detection score, same as reference extraction
        rows.append(np.asarray(face.normed_embedding, dtype=np.float32))
        cids.append(cid)
        paths.append(str(f.relative_to(PHOTOS)))
        nfaces.append(len(faces))
        scores.append(float(face.det_score))
    print(f"{d.name}: {len(files)} photos", flush=True)

np.savez(
    OUT,
    embeddings=np.stack(rows),
    contestant_ids=np.array(cids),
    photo_paths=np.array(paths),
    n_faces=np.array(nfaces),
    det_scores=np.array(scores),
    skipped=np.array(skipped, dtype=object) if skipped else np.array([], dtype=object),
)
print(f"\nwrote {OUT}: {len(rows)} embeddings, {len(skipped)} skipped", flush=True)
