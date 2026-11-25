"""The Circuits tab: view model, page serving, the promote hook and `--if-present` (QCC-71)."""

import argparse
import asyncio
import pathlib

import pytest

from bench import circview
from dashboard import circuits

UNIT = ["CX q0 q22", "HMR q23 b0", "PUSH_CONDITION if b0", "CCX q22 q23 q24", "POP_CONDITION", "SWAP q22 q23"]
TEXT = "\n".join([f"X q{i}" for i in range(22)] + UNIT * 10) + "\n"


def build(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    circ = tmp_path / "best" / "invsqrt" / "tiny.kmb"
    circ.parent.mkdir(parents=True)
    circ.write_text(TEXT)  # kickmix reads text by sniffing, whatever the suffix
    index, view = tmp_path / "idx", tmp_path / "view"
    circview.view_file(circ, index, view)
    return index, view, tmp_path / "best"


def test_entries_describe_the_index(tmp_path: pathlib.Path) -> None:
    index, view, best = build(tmp_path)
    (row,) = circuits.entries(index, view, best)
    assert row["bench"] == "invsqrt" and row["ccx"] == 10 and row["in_best"] == "yes"
    assert row["url"] == f"/circuits/{row['circuit']}.html"
    assert f"[open the explorer]({row['url']})" in circuits.links_markdown([row])


def test_entry_without_a_page_has_no_link(tmp_path: pathlib.Path) -> None:
    index, view, best = build(tmp_path)
    for f in view.glob("*.html"):
        f.unlink()
    (row,) = circuits.entries(index, view, best)
    assert row["url"] == ""
    assert "make circuits" in circuits.links_markdown([row])


def test_no_index_gives_no_rows(tmp_path: pathlib.Path) -> None:
    assert circuits.entries(tmp_path / "none", tmp_path / "none", tmp_path / "none") == []


def test_view_if_present_is_quiet_when_nothing_to_view(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    a = argparse.Namespace(paths=[], if_present=True, index=tmp_path, out=tmp_path, force_index=False)
    assert circview.run(a) == 0
    a.if_present = False
    assert circview.run(a) == 2


def test_after_promotion_ignores_other_benchmarks_and_never_raises(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    circview.after_promotion("dqi", tmp_path)  # unsupported: silent
    bad = tmp_path / "invsqrt"
    bad.mkdir()
    (bad / "broken.kmb").write_bytes(b"not a circuit")
    circview.after_promotion("invsqrt", tmp_path)
    assert "explorer page not built" in capsys.readouterr().out


async def _get(asgi: object, path: str) -> tuple[int, bytes]:
    """One GET straight through the ASGI app (the Starlette test client needs an extra package)."""
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [(b"host", b"localhost")], "client": ("127.0.0.1", 1), "server": ("localhost", 80),
    }  # fmt: skip
    status, body = 0, b""

    sent = False

    async def receive() -> dict[str, object]:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.Event().wait()  # the client stays connected; the app cancels this when it is done
        raise AssertionError("unreachable")

    async def send(msg: dict[str, object]) -> None:
        nonlocal status, body
        if msg["type"] == "http.response.start":
            status = int(msg["status"])  # type: ignore[call-overload]
        elif msg["type"] == "http.response.body":
            body += msg.get("body", b"")  # type: ignore[operator]

    await asyncio.wait_for(asgi(scope, receive, send), 10)  # type: ignore[operator]
    return status, body


def test_pages_are_served_by_the_app(tmp_path: pathlib.Path) -> None:
    pytest.importorskip("indah", reason="dashboard extra not installed")
    from dashboard import app

    _index, view, _best = build(tmp_path)
    page = next(view.glob("*.html"))
    fx = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
    asgi = app.create(fx / "ledger_small.jsonl", fx / "experiments_small.jsonl", pages_dir=view)
    status, body = asyncio.run(_get(asgi, f"/circuits/{page.name}"))
    assert status == 200 and b"Circuit Explorer" in body
    assert asyncio.run(_get(asgi, "/circuits/missing.html"))[0] == 404
