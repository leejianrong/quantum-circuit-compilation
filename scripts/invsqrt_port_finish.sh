#!/usr/bin/env bash
# Finishing passes of the vendored v12 invsqrt builder from our own wiring (src/invsqrt_gen/port/stages.py finish), same sandbox as scripts/invsqrt_port_stages.sh.
# Same rootless container as scripts/invsqrt_reference_build.sh: no network, inputs read-only, only WORK and OUT writable.
#
#   ARCHIVE=<unpacked invsqrt_source/src> PY313=... PY313_LINK=... VENV=... IMG=... bash scripts/invsqrt_port_finish.sh WORK OUT
#
# Writes OUT/finish.json: a row per pass (cost, hash) and the proof; exits 0 only if the kmb is byte-identical to 321aff83.
set -euo pipefail
: "${ARCHIVE:?}" "${PY313:?}" "${VENV:?}" "${IMG:?}"
PY313_LINK=${PY313_LINK:-$PY313}
WORK=$(realpath -m "${1:?WORK dir}")
OUT=$(realpath -m "${2:?OUT dir}")
REPO=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$WORK" "$OUT"
exec flock /tmp/qcc-heavy.lock podman run --rm --network=none --user 0:0 --entrypoint bash \
  -v "$ARCHIVE:$ARCHIVE:ro" -v "$WORK:$WORK:rw" -v "$OUT:$OUT:rw" \
  -v "$REPO/src/invsqrt_gen/port:$REPO/src/invsqrt_gen/port:ro" -v "$REPO/third_party/syed_invsqrt/src:$REPO/third_party/syed_invsqrt/src:ro" \
  -v "$PY313:$PY313:ro" -v "$PY313_LINK:$PY313_LINK:ro" -v "$VENV:$VENV:ro" \
  -v "$REPO/data:$REPO/data:ro" "$IMG" \
  -c "'$VENV/bin/python' '$REPO/src/invsqrt_gen/port/stages.py' finish --archive '$ARCHIVE' --vendored '$REPO/third_party/syed_invsqrt/src' --official '$REPO/data' --work '$WORK' --out '$OUT/finish.json'"
