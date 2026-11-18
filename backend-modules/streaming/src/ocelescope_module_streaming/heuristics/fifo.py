from typing import Any

from ocelescope_module_streaming.framework import BufferAlgorithm, Heuristic, NoParameters, Stats


class FIFO(Heuristic[NoParameters]):
    """First in, first out: i − ins(k)."""

    label = "FIFO"

    def score(self, key: Any, stats: Stats, position: int, algorithm: BufferAlgorithm[Any, Any]) -> float:
        return position - stats.ins
