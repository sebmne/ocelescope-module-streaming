"""The catalog of available algorithms and heuristics.

Algorithms and heuristics register themselves with `register_algorithm` and
`register_heuristic`. The API exposes the catalog, including JSON schemas of all parameters, so
that clients can render configuration forms without knowing the components in advance.
"""

from ocelescope_module_streaming.catalog.registry import (
    Registry,
    UnknownEntry,
    algorithms,
    heuristics,
    register_algorithm,
    register_heuristic,
)
from ocelescope_module_streaming.catalog.specs import (
    ACTIVITIES_BOUND,
    ARCS_BOUND,
    ENDPOINTS_BOUND,
    AlgorithmSpec,
    BufferSpec,
    ElementScores,
    HeuristicSpec,
    NoParams,
)

__all__ = [
    "ACTIVITIES_BOUND",
    "ARCS_BOUND",
    "ENDPOINTS_BOUND",
    "AlgorithmSpec",
    "BufferSpec",
    "ElementScores",
    "HeuristicSpec",
    "NoParams",
    "Registry",
    "UnknownEntry",
    "algorithms",
    "heuristics",
    "register_algorithm",
    "register_heuristic",
]
