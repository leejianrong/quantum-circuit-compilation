#!/usr/bin/env bash
# Our driver for the v17 invsqrt generator (src/invsqrt_gen/port/v17.py) in the same sandbox as
# scripts/invsqrt_v17_reference_build.sh: rootless podman, no network, inputs read-only, only WORK and OUT writable.
# Writes OUT/ledger.json (a row per stage export) and OUT/invsqrt.kmb; exits 0 only if the kmb is byte-identical to 70fe5f79.
#
#   GEN=<.../invsqrt_generator/invsqrt_generator> PY313=... PY313_LINK=... VENV=<venv with numpy and scipy> IMG=... \
#   bash scripts/invsqrt_v17_port.sh WORK OUT
set -euo pipefail
: "${GEN:?}" "${PY313:?}" "${VENV:?}" "${IMG:?}"
PY313_LINK=${PY313_LINK:-$PY313}
WORK=$(realpath -m "${1:?WORK dir}")
OUT=$(realpath -m "${2:?OUT dir}")
REPO=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$WORK" "$OUT"
exec flock /tmp/qcc-heavy.lock podman run --rm --network=none --user 0:0 --entrypoint bash \
  -v "$GEN:$GEN:ro" -v "$WORK:$WORK:rw" -v "$OUT:$OUT:rw" \
  -v "$REPO/src/invsqrt_gen/port:$REPO/src/invsqrt_gen/port:ro" -v "$REPO/third_party/syed_invsqrt_v17/src:$REPO/third_party/syed_invsqrt_v17/src:ro" \
  -v "$PY313:$PY313:ro" -v "$PY313_LINK:$PY313_LINK:ro" -v "$VENV:$VENV:ro" \
  -v "$REPO/data:$REPO/data:ro" "$IMG" \
  -c "PYTHONPATH='$REPO/data/kickmix' '$VENV/bin/python' -B '$REPO/src/invsqrt_gen/port/v17.py' build --gen '$GEN' --vendored '$REPO/third_party/syed_invsqrt_v17/src' --work '$WORK/run' --out '$OUT'"
