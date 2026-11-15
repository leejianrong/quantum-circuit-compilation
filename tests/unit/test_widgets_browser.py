"""Smoke test of the learning-track widgets in a real browser. Skipped without Playwright and Chromium
(`uv sync --extra shots` and `playwright install chromium`); CI does not install them."""

import functools
import http.server
import shutil
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    work = tmp_path_factory.mktemp("work")
    # Zensical wants docs_dir inside the project root, so build a copy of docs/ and the config in a temp dir.
    shutil.copytree(ROOT / "docs", work / "docs")
    shutil.copy(ROOT / "zensical.toml", work / "zensical.toml")
    res = subprocess.run(
        [sys.executable, "-m", "zensical", "build", "-f", "zensical.toml"],
        capture_output=True,
        text=True,
        cwd=work,
    )
    out = work / "site"
    if res.returncode != 0 or not (out / "index.html").exists():
        pytest.skip(f"could not build the site here: {res.stderr[-200:]}")
    handler = functools.partial(Quiet, directory=str(out))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_widgets_mount_and_respond(base: str) -> None:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"chromium is not installed: {e}")
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        for path, name in (
            ("learn/qubits-and-gates", "interference"),
            ("learn/costs-and-mbuc", "iso-cost"),
            ("learn/costs-and-mbuc", "mbuc"),
            ("learn/primer-dfthcsos", "dfthcsos"),
        ):
            page.goto(f"{base}/{path}/")
            page.wait_for_selector(f'.qcc-widget[data-widget="{name}"][data-mounted="1"]')
        page.goto(f"{base}/learn/primer-dfthcsos/")
        w = page.locator('.qcc-widget[data-widget="dfthcsos"]')
        w.locator("button", has_text="baseline").click()
        assert "3,355,6" in w.locator(".qcc-readout p").nth(1).inner_text()
        page.goto(f"{base}/learn/costs-and-mbuc/")
        m = page.locator('.qcc-widget[data-widget="mbuc"]')
        assert m.locator("li.good").count() == 1
        m.locator("label", has_text="apply the CZ repair").locator("input").uncheck()
        assert m.locator("li.bad").count() == 1  # a=1, b=1, m=1 without the repair leaves the wrong sign
        browser.close()
        assert errors == []
