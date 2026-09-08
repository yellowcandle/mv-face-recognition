"""Ticket 001 phase B: within- vs between-person cosine, and the gate verdict.

Reads photo_embeddings.npz from phase A. Numbers only; no production code touched.
"""
import csv
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
REPO = Path("/Users/yellowcandle/dev/mv-face-recognition")
GATE_MATCH, GATE_CROSS = 0.45, 0.2
PROD_ACCEPT_COS = 1 - 0.68  # processing_config.yaml:34 tolerance, as a cosine

# allow_pickle is safe here: this npz is written by extract_photo_embeddings.py alongside
# it in the scratch dir, and only needs it for the object-dtype `skipped` array.
d = np.load(HERE / "photo_embeddings.npz", allow_pickle=True)
E = d["embeddings"].astype(np.float32)
E /= np.linalg.norm(E, axis=1, keepdims=True)  # same normalise+matmul as compute_similarity.py:74-79
cid, nfaces, skipped = d["contestant_ids"], d["n_faces"], d["skipped"]

names = {}
with open(REPO / "metadata/contestant_info.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        names[r["編號"].strip()] = r["暱稱"].strip()

ids = sorted(set(cid.tolist()), key=int)
S = E @ E.T
np.fill_diagonal(S, np.nan)

print(f"photos embedded {len(E)} / 741 on disk | contestants {len(ids)} / 96 | "
      f"no face detected {len(skipped)}")
multi = nfaces > 1
print(f"group-shot contamination: {multi.sum()}/{len(E)} photos ({100 * multi.mean():.1f}%) "
      f"have >1 face, and faces[0] picks by detection score, not identity")

print("\n{:>4} {:<14} {:>3} {:>7} {:>7} {:>7}".format("id", "nickname", "n", "mean", "min", "max"))
rows, within, singles = [], [], []
for c in ids:
    i = np.flatnonzero(cid == c)
    n_multi = int(multi[i].sum())
    if len(i) < 2:
        singles.append(c)
        print(f"{c:>4} {names.get(c, '?'):<14} {len(i):>3}   single photo, no within-person pair")
        continue
    blk = S[np.ix_(i, i)]
    v = blk[~np.isnan(blk)]
    within.append(v)
    rows.append((c, v.mean(), v.max()))
    print(f"{c:>4} {names.get(c, '?'):<14} {len(i):>3} {v.mean():>7.3f} {v.min():>7.3f} "
          f"{v.max():>7.3f}  {n_multi} multi-face")

W = np.concatenate(within)
B = S[(cid[:, None] != cid[None, :]) & ~np.isnan(S)]


def dist(label, v):
    q = np.percentile(v, [5, 50, 95, 99])
    print(f"{label:<22} n={len(v):>6} mean={v.mean():.3f} sd={v.std():.3f} "
          f"min={v.min():.3f} max={v.max():.3f} | p5={q[0]:.3f} p50={q[1]:.3f} "
          f"p95={q[2]:.3f} p99={q[3]:.3f}")


print()
dist("within-person pairs", W)
dist("between-person pairs", B)

cmax = np.array([r[2] for r in rows])
cmean = np.array([r[1] for r in rows])
print(f"\nper-contestant within-person MAX : mean={cmax.mean():.3f} median={np.median(cmax):.3f} "
      f"min={cmax.min():.3f} max={cmax.max():.3f}")
print(f"per-contestant within-person MEAN: mean={cmean.mean():.3f} median={np.median(cmean):.3f} "
      f"min={cmean.min():.3f} max={cmean.max():.3f}")
print(f"contestants whose within-person max  >= {GATE_MATCH}: {(cmax >= GATE_MATCH).sum()}/{len(cmax)}")
print(f"contestants whose within-person mean >= {GATE_MATCH}: {(cmean >= GATE_MATCH).sum()}/{len(cmean)}")
print(f"between-person pairs above {GATE_CROSS}: {100 * (B > GATE_CROSS).mean():.1f}%")
print(f"between-person pairs above production accept cosine {PROD_ACCEPT_COS:.2f}: "
      f"{100 * (B > PROD_ACCEPT_COS).mean():.1f}%")
if singles:
    print(f"single-photo contestants: {', '.join(singles)}")

print(f"\nGATE (matched mean >= {GATE_MATCH}, cross-person <= {GATE_CROSS})")
print(f"  by within-person MAX per contestant : {cmax.mean():.3f} vs cross {B.mean():.3f} -> "
      f"{'CLEARS' if cmax.mean() >= GATE_MATCH and B.mean() <= GATE_CROSS else 'FAILS'}")
print(f"  by within-person MEAN per contestant: {cmean.mean():.3f} vs cross {B.mean():.3f} -> "
      f"{'CLEARS' if cmean.mean() >= GATE_MATCH and B.mean() <= GATE_CROSS else 'FAILS'}")
