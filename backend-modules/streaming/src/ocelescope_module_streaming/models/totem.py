from ocelescope import Resource
from ocelescope.visualization.default.graph import DIRECTED_ELK_GRAPH_LAYOUT, Graph, GraphEdge, GraphNode
from ocelescope.visualization.util.color import generate_color_map
from pydantic import BaseModel, Field


class TotemEdge(BaseModel):
    """How objects of `source` relate to objects of `target`; None where no relation holds.

    Attributes:
        source: The source object type.
        target: The target object type.
        temporal: The temporal relation of their lifespans, e.g. "during" or "precedes".
        log_cardinality: How many `target` objects a `source` object relates to over the log.
        event_cardinality: How many `target` objects an event of a `source` object has.
    """

    source: str
    target: str
    temporal: str | None = None
    log_cardinality: str | None = None
    event_cardinality: str | None = None


class Totem(Resource):
    """A temporal object type model (TOTeM)."""

    label = "Temporal Object Type Model"
    description = "Temporal relations and cardinalities between object types"

    object_types: list[str] = Field(default_factory=list)
    edges: list[TotemEdge] = Field(default_factory=list)

    def visualize(self) -> Graph:
        colors = generate_color_map(self.object_types, "custom")
        nodes = [
            GraphNode(id=t, label=t, shape="rectangle", width=140, height=40, color=colors[t], border_color="#000000")
            for t in self.object_types
        ]
        edges = [
            GraphEdge(
                id=f"{edge.source}->{edge.target}",
                source=edge.source,
                target=edge.target,
                end_arrow="triangle",
                label=" · ".join(
                    f"{name}: {value}"
                    for name, value in (
                        ("TR", edge.temporal),
                        ("LC", edge.log_cardinality),
                        ("EC", edge.event_cardinality),
                    )
                    if value
                ),
            )
            for edge in self.edges
        ]
        return Graph(nodes=nodes, edges=edges, layout_config=DIRECTED_ELK_GRAPH_LAYOUT)
