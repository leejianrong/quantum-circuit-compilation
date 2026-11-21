#!/usr/bin/env bash
# Rebuild the 43-qubit public invsqrt circuit (syed3000 v17, 70fe5f79) from its downloaded generator (Apache-2.0, never
# committed) inside a rootless container, same way as scripts/invsqrt_reference_build.sh: no network, inputs read-only,
# only WORK and OUT writable. Owner approved this one build on 2026-11-21 (QCC-68); it traces opened files and executed
# modules (QCC_TRACE) and checks the output hash. Nothing from it is imported into our environment.
#
# The dataset stores the generator expanded, so `syed_source.zip`, which build.py unpacks and hash-checks, does not exist.
# This script builds from a COPY of the tree in which only that step is replaced (copy the `syed_source` directory instead
# of unzipping; the final SHA-256 assertion and every stage's expected hash stay), and appends the trace hook to the copy's
# own sitecustomize.py (it shadows the venv's on the subprocess path). Kaggle also stored every `*.json.gz` witness
# decompressed, so the copy gets a gzip sibling for each `<name>.json` whose `<name>.json.gz` the sources mention (the code
# only reads their content). The downloaded tree is never edited.
#
#   GEN=<.../invsqrt_generator/invsqrt_generator> PY313=... PY313_LINK=... VENV=<venv with numpy and scipy> IMG=... \
#   TRACE=<file> bash scripts/invsqrt_v17_reference_build.sh WORK OUT
#
# Expected last line of the container run: the final assert passes and OUT/invsqrt.kmb has SHA-256 70fe5f79...
set -euo pipefail
: "${GEN:?}" "${PY313:?}" "${VENV:?}" "${IMG:?}" "${TRACE:?}"
PY313_LINK=${PY313_LINK:-$PY313}
WORK=$(realpath -m "${1:?WORK dir}")
OUT=$(realpath -m "${2:?OUT dir}")
REPO=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$WORK" "$OUT"
: >"$TRACE"
SRC="$WORK/gen"
rm -rf "$SRC"
cp -r "$GEN" "$SRC"
python3 -I - "$SRC" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
b = src / "build.py"
t = b.read_text()
old_assert = "    assert digest(HERE/'syed_source.zip')=='1c3d7d7b66ad4df27ad216d03c3b77a095554580e84e5363b366f4512b7d241d'\n"
old_unzip = "    with zipfile.ZipFile(HERE/'syed_source.zip')as z:z.extractall(work)\n"
assert old_assert in t and old_unzip in t
t = t.replace(old_assert, "").replace(old_unzip, "    shutil.copytree(HERE/'syed_source',work,dirs_exist_ok=True)\n")
b.write_text(t)
import gzip
import re

names = set()
for f in src.rglob("*"):
    if f.is_file() and f.suffix in {".py", ".json", ".md"}:
        names.update(re.findall(r"([A-Za-z0-9_.\-]+\.json)\.gz", f.read_text(errors="ignore")))
made = 0
for f in src.rglob("*.json"):
    gz = f.with_name(f.name + ".gz")
    if f.name in names and not gz.exists():
        with gzip.GzipFile(gz, "wb", mtime=0) as g:
            g.write(f.read_bytes())
        made += 1
print(f"gzip siblings created: {made}")
s = src / "sitecustomize.py"
hook = Path(sys.argv[0]).parent  # unused; the hook text is inlined below
s.write_text(s.read_text() + '''
_T = os.environ.get("QCC_TRACE")
if _T:
    _seen = set()

    def _hook(event, args):
        p = None
        if event == "open" and args and isinstance(args[0], (str, bytes)):
            p = os.fsdecode(args[0]); k = "open"
        elif event == "exec" and args:
            a = args[0]
            fn = getattr(a, "co_filename", None)
            if fn and not fn.startswith("<"):
                p = fn; k = "code"
        if p and (k, p) not in _seen:
            _seen.add((k, p))
            try:
                with open(_T, "a") as f:
                    f.write(f"{k}\\t{p}\\n")
            except Exception:
                pass

    sys.addaudithook(_hook)
''')
PY
exec flock /tmp/qcc-heavy.lock podman run --rm --network=none --user 0:0 --entrypoint bash \
  -v "$WORK:$WORK:rw" -v "$OUT:$OUT:rw" -v "$(dirname "$TRACE"):$(dirname "$TRACE"):rw" \
  -v "$PY313:$PY313:ro" -v "$PY313_LINK:$PY313_LINK:ro" -v "$VENV:$VENV:ro" \
  -v "$REPO/data:$REPO/data:ro" "$IMG" \
  -c "cd '$SRC' && PYTHONPATH='$REPO/data/kickmix' QCC_TRACE='$TRACE' '$VENV/bin/python' -B build.py --out '$OUT/build' && sha256sum '$OUT/build/invsqrt.kmb'"
