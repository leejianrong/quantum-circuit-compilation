"""Regenerate the README and site images from the live ledger (`make plots-readme`).

Draws the six matplotlib plots into docs/img/ (as `bench plots --out docs/img`), then starts the
dashboard on a free port, takes one screenshot per tab with headless Chromium and stops the server.
Cheap: it reads ledger/ and rebuilds one small generator circuit; it verifies nothing.

Needs `uv sync --extra plots --extra dashboard --extra shots` and, once, `uv run playwright install chromium`.
"""

import pathlib
import socket
import sys
import threading
import time

from bench import experiments, ledger, plots

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path("docs/img")
TABS = {
    "Scoreboard": "dashboard-scoreboard.png",
    "Cost explorer": "dashboard-cost.png",
    "Anatomy": "dashboard-anatomy.png",
    "Verifier theatre": "dashboard-theatre.png",
    "Lineage": "dashboard-lineage.png",
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def draw_plots() -> None:
    rows = ledger.read(ledger.DEFAULT_LEDGER)
    for path in plots.render_all(rows, OUT, experiments.read(experiments.DEFAULT_LOG)):
        print(path)


def screenshots() -> None:
    import uvicorn
    from playwright.sync_api import sync_playwright

    sys.path.insert(0, str(ROOT))  # `dashboard/` is not an installed package
    from dashboard import app

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app.create(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.1)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/")
            page.wait_for_timeout(2500)
            for tab, name in TABS.items():
                page.get_by_role("tab", name=tab).click()
                page.wait_for_timeout(2000)  # charts draw client-side
                page.screenshot(path=str(OUT / name), full_page=True)
                print(OUT / name)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(10)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    draw_plots()
    try:
        screenshots()
    except ImportError as e:
        print(f"skipped the dashboard screenshots: {e} (uv sync --extra dashboard --extra shots)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
