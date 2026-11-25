"""Temporal object type models (TOTeM, Liss et al. 2024) as an Ocelescope resource."""

from ocelescope import Resource
from ocelescope.visualization.default.graph import Graph, GraphEdge, GraphNode
from ocelescope.visualization.default.graph.layouting import GraphvizLayoutConfig
from ocelescope.visualization.util.color import generate_color_map
from pydantic import BaseModel, Field

TEMPORAL_RELATIONS = ("during", "during_inv", "precedes", "precedes_inv", "parallel")
LOG_CARDINALITIES = ("1", "0..1", "1..*", "0..*")
EVENT_CARDINALITIES = ("0", "1", "0..1", "1..*", "0..*")
"""Relations from most to least precise; an edge carries the first one with enough support."""

TEMPORAL_SYMBOLS = {"during": "■", "during_inv": "□", "precedes": "▶", "precedes_inv": "▷", "parallel": "||"}


class TotemEdge(BaseModel):
    """The relations from the source type to the target type."""

    source: str
    target: str
    temporal: str | None = None
    log_cardinality: str | None = None
    event_cardinality: str | None = None


class Totem(Resource):
    """A temporal object type model: one edge per direction of every pair of connected types."""

    label = "TOTeM"
    description = "A temporal object type model"

    object_types: list[str] = Field(default_factory=list)
    edges: list[TotemEdge] = Field(default_factory=list)
    tau: float = 1.0

    def visualize(self) -> Graph:
        """Draws the model as in Liss et al.: one line per pair of connected types. Each end of a
        line describes the relation from the type at the other end: the temporal relation as a
        symbol, the log cardinality and, in brackets, the event cardinality."""
        colors = generate_color_map(self.object_types)
        nodes = [
            GraphNode(
                id=t,
                label=t,
                shape="rectangle",
                width=max(110, 9 * len(t) + 30),
                height=40,
                color=colors[t],
                border_color="#000000",
            )
            for t in self.object_types
        ]
        by_pair = {(e.source, e.target): e for e in self.edges}
        pairs = sorted({(min(e.source, e.target), max(e.source, e.target)) for e in self.edges})
        edges = [
            GraphEdge(
                source=a,
                target=b,
                start_label=_end_label(by_pair.get((b, a))),
                end_label=_end_label(by_pair.get((a, b))),
            )
            for a, b in pairs
        ]
        layout = GraphvizLayoutConfig(
            engine="dot", graphAttrs={"rankdir": "LR", "nodesep": 0.9, "ranksep": 2.2, "splines": "spline"}
        )
        return Graph(nodes=nodes, edges=edges, layout_config=layout)


def _end_label(edge: TotemEdge | None) -> str | None:
    if edge is None:
        return None
    symbol = TEMPORAL_SYMBOLS.get(edge.temporal or "", "")
    return f"{symbol} {edge.log_cardinality or '–'} ({edge.event_cardinality or '–'})".strip()
