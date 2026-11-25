"""The buffer-based streaming framework: buffers, heuristics, algorithms and runs.

The framework knows nothing about concrete heuristics or algorithms; they register themselves in
`HEURISTICS` and `ALGORITHMS` when `ocelescope_module_streaming.heuristics` and
`ocelescope_module_streaming.algorithms` are imported.
"""

from ocelescope_module_streaming.framework.algorithm import (
    ALGORITHMS,
    BufferConfig,
    BufferSpec,
    InvalidConfig,
    StreamingAlgorithm,
    UnknownAlgorithm,
    algorithm_class,
    register_algorithm,
)
from ocelescope_module_streaming.framework.buffer import Buffer, Clock, HeuristicError, Record
from ocelescope_module_streaming.framework.coupling import CoupledRemoval, Members
from ocelescope_module_streaming.framework.heuristic import (
    HEURISTICS,
    Heuristic,
    HeuristicConfig,
    NoParams,
    PrivateBuffer,
    PrivateBufferInfo,
    UnknownHeuristic,
    heuristic_class,
    make_heuristic,
    register_heuristic,
)
from ocelescope_module_streaming.framework.run import BufferMonitor, BufferStats, FillSeries, Run, run

__all__ = [
    "ALGORITHMS",
    "HEURISTICS",
    "Buffer",
    "BufferConfig",
    "BufferMonitor",
    "BufferSpec",
    "BufferStats",
    "Clock",
    "CoupledRemoval",
    "FillSeries",
    "Heuristic",
    "HeuristicConfig",
    "HeuristicError",
    "InvalidConfig",
    "Members",
    "NoParams",
    "PrivateBuffer",
    "PrivateBufferInfo",
    "Record",
    "Run",
    "StreamingAlgorithm",
    "UnknownAlgorithm",
    "UnknownHeuristic",
    "algorithm_class",
    "heuristic_class",
    "make_heuristic",
    "register_algorithm",
    "register_heuristic",
    "run",
]
