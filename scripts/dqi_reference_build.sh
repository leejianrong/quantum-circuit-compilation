#!/usr/bin/env bash
# Rebuild the best public DQI circuit from its downloaded source (Apache-2.0, never committed) inside a rootless
# container: no network, inputs read-only, only WORK and OUT writable. The host's glibc is too old for the
# competition kickmix.so (needs GLIBCXX_3.4.32), the container's is not.
#
#   SRC=<extracted dqi_source dir> PY313=<dir of a CPython 3.13 install> PY313_LINK=<path the venv symlink uses> \
#   VENV=<venv with numpy 2.2.4 on that Python> IMG=<image with glibc >= 2.38> \
#   bash scripts/dqi_reference_build.sh WORK OUT
#
# Expected: "BUILT dqi.kmb 7cbe8ecf6f6e9743529b574f019504bb1712ce06fbb570c719ce9d9e2c914cd9", about 90 s, under 2 GB.
# One local deviation: `chmod -R u+w` on the copied tree is refused inside this rootless container, so a copy of
# build.sh beside the source gets `|| true` after it (the copy is already writable). His build.sh is not edited.
set -euo pipefail
: "${SRC:?}" "${PY313:?}" "${VENV:?}" "${IMG:?}"
PY313_LINK=${PY313_LINK:-$PY313}
WORK=$(realpath -m "${1:?WORK dir}")
OUT=$(realpath -m "${2:?OUT dir}")
REPO=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$WORK" "$OUT"
sed 's|^chmod -R u+w "\$ROOT"$|chmod -R u+w "$ROOT" \|\| true|' "$SRC/build.sh" >"$SRC/build.local.sh"
exec flock /tmp/qcc-heavy.lock podman run --rm --network=none --user 0:0 --entrypoint bash \
  -v "$SRC:$SRC:rw" -v "$WORK:$WORK:rw" -v "$OUT:$OUT:rw" \
  -v "$PY313:$PY313:ro" -v "$PY313_LINK:$PY313_LINK:ro" -v "$VENV:$VENV:ro" \
  -v "$REPO/data:$REPO/data:ro" "$IMG" \
  -c "PY='$VENV/bin/python' WORK='$WORK' KEEP_WORK=1 bash '$SRC/build.local.sh' '$REPO/data/kickmix' '$REPO/data/verifiers' '$OUT'"
