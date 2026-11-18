"""Heuristics, one per file. Register new ones in `HEURISTICS`; general ones also in `GENERAL`."""

from ocelescope_module_streaming.framework import Heuristic
from ocelescope_module_streaming.heuristics.fifo import FIFO
from ocelescope_module_streaming.heuristics.lfu import LFU
from ocelescope_module_streaming.heuristics.lfu_da import LFUDA
from ocelescope_module_streaming.heuristics.lifecycle import Lifecycle
from ocelescope_module_streaming.heuristics.lru import LRU
from ocelescope_module_streaming.heuristics.random import RandomReplacement

HEURISTICS: dict[str, type[Heuristic]] = {
    "fifo": FIFO,
    "lru": LRU,
    "lfu": LFU,
    "lfu-da": LFUDA,
    "random": RandomReplacement,
    "lifecycle": Lifecycle,
}
GENERAL = ("fifo", "lru", "lfu", "lfu-da", "random")
"""Heuristics for any buffer; the others suit specific buffers, see `BufferSpec.heuristics`."""

__all__ = ["FIFO", "GENERAL", "HEURISTICS", "LFU", "LFUDA", "LRU", "Lifecycle", "RandomReplacement"]
