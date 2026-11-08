"""Eviction heuristics."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ocelescope_module_streaming.framework.buffer import Entry

if TYPE_CHECKING:
    from ocelescope_module_streaming.framework.algorithm import StreamingAlgorithm


class Heuristic(ABC):
    """Base class for eviction heuristics.

    A heuristic scores buffered keys. When a buffer exceeds its capacity, the key with the
    highest score is evicted.

    Heuristics may read any state of the algorithm. State a heuristic maintains itself should
    be stored in a buffer, so that it counts toward the memory bound.
    """

    @abstractmethod
    def score(
        self, key: Any, entry: Entry[Any], algorithm: "StreamingAlgorithm[Any]", position: int, timestamp: datetime
    ) -> float:
        """Scores a buffered key.

        Args:
            key: The buffered key.
            entry: The entry stored under `key`.
            algorithm: The algorithm owning the buffer.
            position: The position of the current item.
            timestamp: The timestamp of the current item.

        Returns:
            The eviction score; higher scores are evicted first.
        """

    def __repr__(self) -> str:
        return type(self).__name__
