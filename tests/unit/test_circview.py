"""`bench view`: the page is the template with the index inlined, and it is valid JavaScript (QCC-71)."""

import json
import pathlib
import re
import shutil
import subprocess

import pytest

from bench import circindex, circview

HEADER = [f"X q{i}" for i in range(22)]
UNIT = ["CX q0 q22", "HMR q23 b0", "PUSH_CONDITION if b0", "CCX q22 q23 q24", "POP_CONDITION", "SWAP q22 q23"]
BODY = UNIT * 10
TEXT = "\n".join(HEADER + BODY) + "\n"


def make(tmp_path: pathlib.Path) -> pathlib.Path:
    circ = tmp_path / "tiny.kmx"
    circ.write_text(TEXT)
    return circview.view_file(circ, tmp_path / "idx", tmp_path / "view", bench="invsqrt")


def data_of(html: str) -> dict[str, object]:
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    assert m
    return json.loads(m.group(1))  # type: ignore[no-any-return]


def test_page_inlines_summary_and_every_line(tmp_path: pathlib.Path) -> None:
    page = make(tmp_path)
    d = data_of(page.read_text())
    assert d["rows"][0] == [0, "X q0", 0]  # type: ignore[index]
    assert len(d["rows"]) == d["summary"]["instructions"]  # type: ignore[index,arg-type]
    assert page.name == d["summary"]["sha256"][:8] + ".html"  # type: ignore[index]


def test_data_cannot_close_the_script(tmp_path: pathlib.Path) -> None:
    entry = circindex.index_file(_circ(tmp_path), tmp_path / "idx", bench="invsqrt", k=2, samples=16)[1]
    page0 = entry / "pages" / "000.json"
    d = json.loads(page0.read_text())
    d["rows"][0][1] = "X q0 </script><b>"
    page0.write_text(json.dumps(d))
    html = circview.render(entry)
    assert html.count("</script>") == 2  # the data script and the page script, nothing injected
    assert data_of(html)["rows"][0][1] == "X q0 </script><b>"  # type: ignore[index]


def test_render_is_deterministic(tmp_path: pathlib.Path) -> None:
    a = make(tmp_path).read_text()
    assert make(tmp_path).read_text() == a


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_page_script_parses(tmp_path: pathlib.Path) -> None:
    html = make(tmp_path).read_text()
    js = re.findall(r"<script>(.*?)</script>", html, re.S)[-1]
    f = tmp_path / "page.js"
    f.write_text(js)
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _circ(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "t2.kmx"
    p.write_text(TEXT)
    return p
