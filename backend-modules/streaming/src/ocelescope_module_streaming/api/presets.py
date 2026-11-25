"""Ready-made configurations. Capacity 125 is the buffer size of Liss et al.'s Fig. 3."""

from ocelescope_module_streaming.api.catalog import Preset
from ocelescope_module_streaming.framework import BufferConfig, HeuristicConfig


def _buffer(capacity: int, heuristic: str = "fifo", **params: object) -> BufferConfig:
    return BufferConfig(capacity=capacity, heuristic=HeuristicConfig(name=heuristic, params=dict(params)))


LIFECYCLE = {"t_int": 200, "t_max": 2000, "c_hist": 100}

PRESETS: list[Preset] = [
    Preset(
        key="liss_ocdfg_fifo",
        label="OC-DFG (Liss et al.) · FIFO 125",
        description="Both buffers of Liss et al.'s OC-DFG with capacity 125 and FIFO.",
        algorithm="liss_ocdfg",
        buffers={"objects": _buffer(125), "arcs": _buffer(125)},
    ),
    Preset(
        key="liss_ocdfg_lifecycle",
        label="OC-DFG (Liss et al.) · lifecycle objects",
        description="The object buffer evicts with the lifecycle heuristic, the arc buffer with FIFO.",
        algorithm="liss_ocdfg",
        buffers={"objects": _buffer(125, "lifecycle", **LIFECYCLE), "arcs": _buffer(125)},
    ),
    Preset(
        key="liss_totem_fifo",
        label="TOTeM (Liss et al.) · FIFO 125",
        description="All three TOTeM buffers with capacity 125 and FIFO, as in Liss et al.'s Fig. 3.",
        algorithm="liss_totem",
        buffers={name: _buffer(125) for name in ("lifespans", "log_cardinality", "event_cardinality")},
    ),
    Preset(
        key="liss_totem_lru",
        label="TOTeM (Liss et al.) · LRU 125",
        description="All three TOTeM buffers with capacity 125 and LRU.",
        algorithm="liss_totem",
        buffers={name: _buffer(125, "lru") for name in ("lifespans", "log_cardinality", "event_cardinality")},
    ),
    Preset(
        key="liss_totem_lifecycle",
        label="TOTeM (Liss et al.) · lifecycle lifespans",
        description="The lifespan buffer evicts with the lifecycle heuristic, the row buffers with FIFO.",
        algorithm="liss_totem",
        buffers={
            "lifespans": _buffer(125, "lifecycle", **LIFECYCLE),
            "log_cardinality": _buffer(125),
            "event_cardinality": _buffer(125),
        },
    ),
    Preset(
        key="df_lru",
        label="Directly-follows (A_df) · LRU objects",
        description="100 objects with LRU; the counters are large enough to never evict on small logs.",
        algorithm="df",
        buffers={
            "obj": _buffer(100, "lru"),
            "arc": _buffer(1000, "lru"),
            "start": _buffer(200, "lru"),
            "end": _buffer(200, "lru"),
        },
    ),
    Preset(
        key="df_lifecycle",
        label="Directly-follows (A_df) · lifecycle objects",
        description="100 objects with the lifecycle heuristic; large counters with LRU.",
        algorithm="df",
        buffers={
            "obj": _buffer(100, "lifecycle", **LIFECYCLE),
            "arc": _buffer(1000, "lru"),
            "start": _buffer(200, "lru"),
            "end": _buffer(200, "lru"),
        },
    ),
]
