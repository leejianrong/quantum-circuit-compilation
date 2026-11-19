#!/usr/bin/env bash
# Rebuild the 46-qubit public invsqrt circuit from its downloaded source (Apache-2.0, never committed) inside a rootless
# container, the same way as scripts/dqi_reference_build.sh: no network, inputs read-only, only WORK and OUT writable.
# The competition kickmix.so needs a newer glibc/libstdc++ than the host has; the image's is new enough.
# Owner approved this one build on 2026-11-19 (QCC-68). It exists to trace which files the builder opens (QCC_TRACE,
# written by a sitecustomize in the venv) and to check the output hash; nothing from it is imported into our environment.
#
#   SRC=<dir holding build.sh> PY313=<real CPython 3.13 dir> PY313_LINK=<dir the venv symlink points through> \
#   VENV=<venv with numpy on that Python> IMG=<image with glibc >= 2.38> TRACE=<file> \
#   bash scripts/invsqrt_reference_build.sh WORK OUT
#
# Expected last line: "BUILT invsqrt.kmb 321aff83636214196daa9cbc9dcc9c5e12a155bcff8d9989e98b8cee40935177".
set -euo pipefail
: "${SRC:?}" "${PY313:?}" "${VENV:?}" "${IMG:?}" "${TRACE:?}"
PY313_LINK=${PY313_LINK:-$PY313}
WORK=$(realpath -m "${1:?WORK dir}")
OUT=$(realpath -m "${2:?OUT dir}")
REPO=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$WORK" "$OUT"
: >"$TRACE"
# his build.sh does `chmod -R u+w` on a tree it copied; refused in a rootless container, so a local copy gets `|| true`
sed 's|^chmod -R u+w "\$X"$|chmod -R u+w "$X" \|\| true|' "$SRC/build.sh" >"$SRC/build.local.sh"
exec flock /tmp/qcc-heavy.lock podman run --rm --network=none --user 0:0 --entrypoint bash \
  -v "$SRC:$SRC:rw" -v "$WORK:$WORK:rw" -v "$OUT:$OUT:rw" -v "$(dirname "$TRACE"):$(dirname "$TRACE"):rw" \
  -v "$PY313:$PY313:ro" -v "$PY313_LINK:$PY313_LINK:ro" -v "$VENV:$VENV:ro" \
  -v "$REPO/data:$REPO/data:ro" "$IMG" \
  -c "PY='$VENV/bin/python' WORK='$WORK' QCC_TRACE='$TRACE' bash '$SRC/build.local.sh' '$REPO/data/kickmix' '$REPO/data/verifiers' '$OUT'"
