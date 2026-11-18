from typing import Any

from ocelescope_module_streaming.framework import BufferAlgorithm, Heuristic, NoParameters, Stats


class LRU(Heuristic[NoParameters]):
    """Least recently used: i − last(k)."""

    label = "LRU"

    def score(self, key: Any, stats: Stats, position: int, algorithm: BufferAlgorithm[Any, Any]) -> float:
        return position - stats.last
