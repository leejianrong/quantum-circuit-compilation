#!/usr/bin/env bash
# Per-patch ledger of the vendored v12 invsqrt builder, from our own wiring (src/invsqrt_gen/port/stages.py), inside the same
# rootless container as scripts/invsqrt_reference_build.sh: no network, inputs read-only, only WORK and OUT writable.
#
#   ARCHIVE=<unpacked invsqrt_source/src> PY313=... PY313_LINK=... VENV=... IMG=... bash scripts/invsqrt_port_stages.sh WORK OUT
#
# Writes OUT/ledger.json: qubits, mean Toffolis, rotations and the modelled cost after each prefix of the 13 patches.
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
  -c "'$VENV/bin/python' '$REPO/src/invsqrt_gen/port/stages.py' ledger --archive '$ARCHIVE' --vendored '$REPO/third_party/syed_invsqrt/src' --official '$REPO/data' --work '$WORK' --out '$OUT/ledger.json'"
