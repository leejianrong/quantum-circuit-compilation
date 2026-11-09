#!/usr/bin/env bash
# Downloads the competition files into data/ (gitignored). The full set is about 1.1 GB
# (the baseline dqi.kmb alone is 886 MB); pass file names to fetch only some.
set -euo pipefail
COMP=google-verifiable-quantum-circuit-compilation
cd "$(dirname "$0")/.."
mkdir -p data && cd data
if [ "$#" -eq 0 ]; then
  kaggle competitions download "$COMP" -q && unzip -oq "$COMP.zip" && rm "$COMP.zip"
else
  for f in "$@"; do kaggle competitions download "$COMP" -f "$f" -q; done
fi
