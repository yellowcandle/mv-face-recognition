#!/usr/bin/env bash
# Submit the cache build, wait for it, then run the five videos in parallel on HF Jobs.
#
# Prerequisites:
#   - the hf-jobs branch pushed (the job downloads it as a tarball)
#   - inputs/contestant_info.csv and models/home/.insightface uploaded to the bucket
#   - hf auth login with write access to the bucket
set -euo pipefail

BUCKET="${BUCKET:-yellowcandle/mv-face-recognition}"
VOLUME="hf://buckets/${BUCKET}:/mnt/data"
FLAVOR="${FLAVOR:-cpu-upgrade}"
SCRIPT="$(cd "$(dirname "$0")" && pwd)/hf_pipeline.py"

submit() {
  hf jobs uv run --detach --quiet --flavor "$FLAVOR" --volume "$VOLUME" "$@" "$SCRIPT"
}

echo "== reference cache"
cache_id=$(submit --timeout 45m --name mv-cache -- cache)
echo "job $cache_id"
hf jobs wait "$cache_id"

echo "== videos"
ids=()
for id in 1 2 3 4 5; do
  job=$(submit --timeout 2h --name "mv-video-$id" -- video --video-id "$id")
  echo "video $id -> job $job"
  ids+=("$job")
done

hf jobs wait "${ids[@]}"
echo "outputs: hf://buckets/${BUCKET}/output/"
