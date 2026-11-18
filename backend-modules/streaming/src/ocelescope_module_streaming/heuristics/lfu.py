from typing import Any

from ocelescope_module_streaming.framework import BufferAlgorithm, Heuristic, NoParameters, Stats


class LFU(Heuristic[NoParameters]):
    """Least frequently used: −freq(k)."""

    label = "LFU"

    def score(self, key: Any, stats: Stats, position: int, algorithm: BufferAlgorithm[Any, Any]) -> float:
        return -stats.freq
