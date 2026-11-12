import pathlib

import pytest

pytest.importorskip("indah", reason="dashboard extra not installed")

from dashboard import app  # noqa: E402

FIX = pathlib.Path(__file__).resolve().parents[1] / "fixtures"


def labels(component: object) -> list[str]:
    return list(component._labels)  # type: ignore[attr-defined]


def test_app_builds_from_a_fixture_ledger() -> None:
    root = app.build_app(FIX / "ledger_small.jsonl", FIX / "experiments_small.jsonl")
    tabs = next(c for c in root.children if type(c).__name__ == "Tabs")
    assert labels(tabs) == [name for name, _ in app.TABS]
    assert labels(tabs)[:2] == ["Scoreboard", "Experiments"]


def test_app_builds_with_no_ledger_at_all(tmp_path: pathlib.Path) -> None:
    app.build_app(tmp_path / "none.jsonl", tmp_path / "none-exp.jsonl")


def test_asgi_app_is_created() -> None:
    from starlette.applications import Starlette

    assert isinstance(app.create(FIX / "ledger_small.jsonl", FIX / "experiments_small.jsonl"), Starlette)
