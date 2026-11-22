#!/usr/bin/env bash
# Build a profile of syed3000's v17 DQI generator (Apache-2.0, never committed) inside a rootless container, like
# scripts/dqi_reference_build.sh: no network, inputs read-only, only OUT writable, memory capped. Owner approved the
# `paired-plain` profile build on 2026-11-22 (QCC-19). The circuit is verified separately on Kaggle (ADR-0002).
#
#   GEN=<.../dqi_generator/dqi_generator> PY313=... PY313_LINK=... VENV=<venv with numpy> IMG=... \
#   PROFILE=paired-plain bash scripts/dqi_v17_build.sh OUT
#
# The download stores `vendor/d70-source.zip` expanded, so build.py's zip read cannot work. The script builds from a COPY of the
# generator patched by scripts/dqi_v17_patch_copy.py (the zip becomes a directory with the same member list and the same per-file
# SHA-256 checks; the archive-level hash cannot be checked). The download is untouched.
# Expected (paired-plain): dqi.kmb with SHA-256 fc2564c61931a0b1c789d8857a78e54f88466b546870f0e99ad252b8c59183c5, which the
# generator checks against its own manifest. Needs about 5.5 GB of free disk in OUT.
set -euo pipefail
: "${GEN:?}" "${PY313:?}" "${VENV:?}" "${IMG:?}"
PY313_LINK=${PY313_LINK:-$PY313}
PROFILE=${PROFILE:-paired-plain}
OUT=$(realpath -m "${1:?OUT dir}")
REPO=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$OUT"
SRC="$OUT/gen"
rm -rf "$SRC"
cp -r "$GEN" "$SRC"
python3 -I "$REPO/scripts/dqi_v17_patch_copy.py" "$SRC"
exec flock /tmp/qcc-heavy.lock podman run --rm --network=none --user 0:0 --memory=20g --entrypoint bash \
  -v "$OUT:$OUT:rw" \
  -v "$PY313:$PY313:ro" -v "$PY313_LINK:$PY313_LINK:ro" -v "$VENV:$VENV:ro" \
  -v "$REPO/data:$REPO/data:ro" "$IMG" \
  -c "cd '$OUT' && PYTHONPATH='$REPO/data/kickmix' VQCC_COMPETITION_DIR='$REPO/data' '$VENV/bin/python' -B '$SRC/build.py' --profile '$PROFILE' --out '$OUT/build' && sha256sum '$OUT/build/dqi.kmb'"
