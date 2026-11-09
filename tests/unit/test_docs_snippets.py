"""Run every ```python block in docs/learn/**/*.md so the learning pages cannot rot.

Blocks within one page share a namespace and run top to bottom, so a later block can use names
defined earlier. A fence written as ```python no-run is skipped.
"""

import re
from pathlib import Path

import pytest

LEARN = Path(__file__).resolve().parents[2] / "docs" / "learn"
# The fence may be indented (blocks inside admonitions and collapsible solutions).
FENCE = re.compile(r"^([ \t]*)```python([^\n]*)\n(.*?)^\1```[ \t]*$", re.DOTALL | re.MULTILINE)


def extract(text: str) -> list[tuple[int, str]]:
    """Return (line number, source) for each runnable python block."""
    blocks = []
    for m in FENCE.finditer(text):
        if "no-run" in m.group(2).split():
            continue
        indent = len(m.group(1))
        body = "".join(ln[indent:] for ln in m.group(3).splitlines(keepends=True))
        blocks.append((text.count("\n", 0, m.start()) + 1, body))
    return blocks


def test_extract_skips_no_run() -> None:
    text = "a\n```python\nx = 1\n```\n```python no-run\nboom\n```\n"
    assert extract(text) == [(2, "x = 1\n")]


def test_extract_handles_indented_blocks() -> None:
    text = "??? note\n    ```python\n    if True:\n        y = 2\n    ```\n"
    assert extract(text) == [(2, "if True:\n    y = 2\n")]


def test_broken_snippet_is_reported() -> None:
    with pytest.raises(ZeroDivisionError):
        exec(compile(extract("```python\n1 / 0\n```\n")[0][1], "<snippet>", "exec"), {})


PAGES = sorted(LEARN.rglob("*.md"))


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(LEARN)))
def test_page_snippets_run(page: Path) -> None:
    namespace: dict[str, object] = {"__name__": "__docs__"}
    for line, source in extract(page.read_text(encoding="utf-8")):
        code = compile(source, f"{page.name}:{line}", "exec")
        exec(code, namespace)
