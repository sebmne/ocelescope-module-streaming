from typing import Any

from ocelescope_module_streaming.framework import Buffer, BufferAlgorithm, Heuristic, NoParameters, normalized
from ocelescope_module_streaming.heuristics.fifo import FIFO
from ocelescope_module_streaming.heuristics.lfu import LFU


class LFUDA(Heuristic[NoParameters]):
    """LFU with dynamic aging: the normalized FIFO and LFU scores, summed."""

    label = "LFU-DA"

    def __init__(self, parameters: NoParameters) -> None:
        super().__init__(parameters)
        self._fifo, self._lfu = FIFO(parameters), LFU(parameters)

    def scores(self, buffer: Buffer[Any, Any], position: int, algorithm: BufferAlgorithm[Any, Any]) -> dict[Any, float]:
        age = normalized(self._fifo.scores(buffer, position, algorithm))
        rarity = normalized(self._lfu.scores(buffer, position, algorithm))
        return {key: age[key] + rarity[key] for key in age}
