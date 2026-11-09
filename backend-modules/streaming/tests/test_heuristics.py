from typing import Any

import pytest
from support import step

from ocelescope_module_streaming.framework import Buffer, BufferConfig, Heuristic
from ocelescope_module_streaming.heuristics import FIFO, LFU, LIFO, LRU, RandomReplacement


def victim(heuristic: Heuristic) -> Any:
    """Writes a@1, b@2, c@3, a@4, a@5, b@6 into a buffer and returns the victim at step 7."""
    buffer: Buffer[str, int] = Buffer("b", BufferConfig(capacity=2, heuristic=heuristic))
    for position, key in enumerate("abcaab", start=1):
        step(buffer, position)
        buffer.put(key, position)
    step(buffer, 7)
    return buffer.victim()


@pytest.mark.parametrize(
    ("heuristic", "expected"),
    [(FIFO(), "a"), (LIFO(), "c"), (LRU(), "c"), (LFU(), "c")],
)
def test_cache_policies_pick_expected_victim(heuristic: Heuristic, expected: str) -> None:
    assert victim(heuristic) == expected


def test_random_is_repeatable_per_seed() -> None:
    assert [victim(RandomReplacement(seed=3)) for _ in range(5)] == [
        victim(RandomReplacement(seed=3)) for _ in range(5)
    ]
