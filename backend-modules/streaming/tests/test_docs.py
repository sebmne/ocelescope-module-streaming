"""Runs the Python examples of the guides, so the documentation stays correct.

All ```python blocks of a guide run in order in one namespace. Components the examples
register in the catalog are removed afterwards.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from ocelescope_module_streaming.catalog import algorithms, heuristics

DOCS = Path(__file__).resolve().parents[3] / "docs"
GUIDES = ["guide-eviction-heuristics.md", "guide-streaming-algorithms.md"]


@pytest.fixture
def isolated_catalog() -> Iterator[None]:
    """Restores the catalog after the examples registered their components."""
    for registry in (algorithms, heuristics):
        for _ in registry:  # load the built-ins first
            break
    saved_algorithms = dict(algorithms._entries)  # noqa: SLF001
    saved_heuristics = dict(heuristics._entries)  # noqa: SLF001
    yield
    algorithms._entries.clear()  # noqa: SLF001
    algorithms._entries.update(saved_algorithms)  # noqa: SLF001
    heuristics._entries.clear()  # noqa: SLF001
    heuristics._entries.update(saved_heuristics)  # noqa: SLF001


@pytest.mark.parametrize("guide", GUIDES)
@pytest.mark.usefixtures("isolated_catalog")
def test_guide_examples_run(guide: str) -> None:
    text = (DOCS / guide).read_text()
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.S)
    assert blocks
    namespace: dict[str, object] = {"__name__": f"docs_{guide.replace('-', '_')}"}
    for index, block in enumerate(blocks):
        try:
            exec(compile(block, f"{guide}[{index}]", "exec"), namespace)  # noqa: S102
        except Exception as error:
            raise AssertionError(f"Example {index} of {guide} failed: {error!r}\n{block}") from error
