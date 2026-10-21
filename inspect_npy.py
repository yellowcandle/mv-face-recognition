import glob
import os
from collections import Counter

import numpy as np

from src.database.roster import Roster

# Path to the embeddings directory (files sit one level down: embeddings/contestants/)
EMBEDDING_DIR = "source/photo/contestants/embeddings"
print(f"[INFO] Checking directory: {os.path.abspath(EMBEDDING_DIR)}")

roster = Roster.from_csv()

# List files in the directory to confirm they are seen by Python's os module
try:
    all_files_in_dir = os.listdir(EMBEDDING_DIR)
    print(f"[INFO] Files found by os.listdir: {all_files_in_dir}")
    npy_files_os_listdir = [f for f in all_files_in_dir if f.endswith("_embedding.npy")]
    print(f"[INFO] .npy files found by os.listdir: {npy_files_os_listdir}")
except Exception as e:
    print(f"[ERROR] Could not list directory {EMBEDDING_DIR}: {e}")
    exit()

# Try glob to find .npy files
glob_pattern = os.path.join(EMBEDDING_DIR, "**", "*_embedding.npy")
print(f"[INFO] Glob pattern: {glob_pattern}")
npy_files_glob = sorted(glob.glob(glob_pattern, recursive=True))
print(f"[INFO] .npy files found by glob.glob: {npy_files_glob}")

if not npy_files_glob:
    print(
        "[ERROR] No embedding files found by glob.glob. Please check the path and pattern."
    )
    if npy_files_os_listdir:
        print(
            "[INFO] os.listdir found .npy files, so the issue might be with glob pattern or special characters."
        )
    exit()

# Resolve every file to its 編號: this is what the database keys on (ADR 0001).
resolved: list[tuple[str, str | None]] = [
    (path, roster.id_for_embedding_stem(os.path.basename(path)[: -len("_embedding.npy")]))
    for path in npy_files_glob
]
unresolved = [path for path, file_id in resolved if file_id is None]
duplicates = [
    file_id
    for file_id, count in Counter(f for _, f in resolved if f).items()
    if count > 1
]

print(
    f"\n[INFO] {len(resolved)} files -> "
    f"{len({file_id for _, file_id in resolved if file_id})} contestants"
)
if unresolved:
    print(f"[WARN] No contestant matches: {unresolved}")
for file_id in duplicates:
    files = [p for p, c in resolved if c == file_id]
    print(f"[WARN] 編號 {file_id} has {len(files)} files; the loader keeps the first: {files}")

for path, resolved_id in resolved:
    print(f"  {resolved_id or '???':>3}  {os.path.basename(path)}")

# Pick the first file found by glob for inspection
file_path = npy_files_glob[0]
print(f"\n[INFO] Inspecting file: {file_path}")
print(f"[INFO] Absolute path of file: {os.path.abspath(file_path)}")
print(f"[INFO] File size: {os.path.getsize(file_path)} bytes")

# Try to load the file
try:
    # allow_pickle=False is safer, True might be needed if they are pickled objects
    data = np.load(file_path, allow_pickle=False)
    print(f"[SUCCESS] Data loaded successfully from {file_path}")
    print(f"  Shape: {data.shape}")
    print(f"  Data type: {data.dtype}")
    print(f"  Size in bytes (according to numpy): {data.nbytes}")
    flat_data = data.flatten()
    print(f"  Flattened shape: {flat_data.shape}")
    print(f"  First 5 values of flattened data: {flat_data[:5]}")
    if flat_data.shape == (512,):
        print(
            "  [CONFIRMATION] Flattened data shape is (512,), as expected by the main script."
        )
    else:
        print(
            f"  [WARNING] Flattened data shape is {flat_data.shape}, NOT (512,). This will be skipped by the main script."
        )

except Exception as e:
    print(f"[ERROR] Error loading file {file_path} with np.load: {e}")
    print("  Attempting with allow_pickle=True...")
    try:
        data = np.load(file_path, allow_pickle=True)
        print(
            f"[SUCCESS] Data loaded successfully from {file_path} with allow_pickle=True"
        )
        print(f"  Object type: {type(data)}")
        if isinstance(data, np.ndarray):
            print(f"  Shape: {data.shape}")
            print(f"  Data type: {data.dtype}")
            print(f"  Size in bytes (according to numpy): {data.nbytes}")
            flat_data = data.flatten()
            print(f"  Flattened shape: {flat_data.shape}")
            print(f"  First 5 values of flattened data: {flat_data[:5]}")
            if flat_data.shape == (512,):
                print(
                    "  [CONFIRMATION] Flattened data shape is (512,), as expected by the main script."
                )
            else:
                print(
                    f"  [WARNING] Flattened data shape is {flat_data.shape}, NOT (512,). This will be skipped by the main script."
                )
        else:
            print(f"  Loaded data is not a NumPy array. It's a {type(data)}.")
            print(f"  Content: {data}")

    except Exception as e2:
        print(
            f"[ERROR] Error loading file {file_path} with np.load (allow_pickle=True): {e2}"
        )

print("\n[INFO] Script finished.")
