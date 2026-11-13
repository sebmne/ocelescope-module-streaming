"""Streaming algorithms, one per file. Register new ones in `ALGORITHMS`."""

from typing import Any

from ocelescope_module_streaming.algorithms.algorithm import StreamingAlgorithm
from ocelescope_module_streaming.algorithms.events import Finished, ItemProcessed, RunEvent
from ocelescope_module_streaming.algorithms.observer import Observer

ALGORITHMS: dict[str, type[StreamingAlgorithm[Any]]] = {}

__all__ = ["ALGORITHMS", "Finished", "ItemProcessed", "Observer", "RunEvent", "StreamingAlgorithm"]
