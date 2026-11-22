"""Patch a COPY of syed3000's v17 DQI generator so it reads its expanded `vendor/d70-source` directory.

The Kaggle download stores `vendor/d70-source.zip` expanded, so `build.py` cannot open the zip. Only that
read changes: the archive-level hash check is dropped (the per-file checks against `manifest.json` and the
member-set check stay), and the zip is replaced by a directory with the same member list.
Usage: dqi_v17_patch_copy.py COPY_DIR.
"""

import sys
from pathlib import Path

SHIM = '''

class _Dir:
    """Stands in for the zip: the same member list, extracted by copy from the expanded directory."""

    def __init__(self, root):
        self.root = root

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def namelist(self):
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file())

    def extract(self, name, tree):
        dest = Path(tree) / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.root / name, dest)
        return str(dest)
'''

b = Path(sys.argv[1]) / "build.py"
t = b.read_text()
chk = (
    "    if digest(archive) != manifest['archive_sha256']:\n"
    "        raise ValueError('Source archive checksum mismatch')\n"
)
use = "        with zipfile.ZipFile(archive) as data:\n"
assert chk in t and use in t and "\n\ndef build(" in t
t = t.replace(chk, "").replace(use, "        with _Dir(HERE / 'vendor' / 'd70-source') as data:\n")
t = t.replace("\n\ndef build(", SHIM + "\n\ndef build(", 1)
b.write_text(t)
print("patched", b)
