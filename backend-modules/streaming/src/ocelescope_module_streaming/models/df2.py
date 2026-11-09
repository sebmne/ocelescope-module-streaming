"""DF2 graphs (definitions.tex: def:df2)."""

from collections.abc import Iterable

from ocelescope import Resource
from ocelescope.visualization.default.graph import (
    DIRECTED_ELK_GRAPH_LAYOUT,
    Graph,
    GraphEdge,
    GraphNode,
    NodeStyle,
)
from pydantic import BaseModel, Field

from ocelescope_module_streaming.blocks import DFSnapshot

_START, _END = "__start__", "__end__"


class DF2Edge(BaseModel):
    """A divergence-free directly-follows edge.

    Attributes:
        source: The source activity.
        target: The target activity.
        count: The summed frequency over the contributing object types.
        object_types: The object types whose relation is not divergent on both activities.
    """

    source: str
    target: str
    count: int
    object_types: list[str]


class DF2Divergence(BaseModel):
    """The object types an activity diverges for."""

    activity: str
    object_types: list[str]


class DF2Graph(Resource):
    """A divergence-free directly-follows (DF2) graph.

    Attributes:
        activities: All observed activities.
        edges: Edges (a, b) with an object type t such that t ∉ div(a) ∩ div(b).
        start_activities: Activities that start an object of a type they do not diverge for.
        end_activities: Activities that end an object of a type they do not diverge for.
        divergence: The divergent object types per activity.
    """

    label = "DF2 Graph"
    description = "A divergence-free directly-follows graph"

    activities: list[str] = Field(default_factory=list)
    edges: list[DF2Edge] = Field(default_factory=list)
    start_activities: list[str] = Field(default_factory=list)
    end_activities: list[str] = Field(default_factory=list)
    divergence: list[DF2Divergence] = Field(default_factory=list)

    def divergent(self) -> dict[str, set[str]]:
        """Returns div(a) per activity."""
        return {entry.activity: set(entry.object_types) for entry in self.divergence}

    def visualize(self) -> Graph:
        nodes = [
            GraphNode(id=activity, label=activity, shape="rectangle", width=140, height=40, color="#ffffff")
            for activity in self.activities
        ]
        nodes += [
            GraphNode(
                id=_START, label="start", shape="circle", width=36, height=36, style=NodeStyle(inner_symbol="triangle")
            ),
            GraphNode(
                id=_END, label="end", shape="circle", width=36, height=36, style=NodeStyle(inner_symbol="square")
            ),
        ]
        edges = [
            GraphEdge(source=edge.source, target=edge.target, end_arrow="triangle", label=str(edge.count))
            for edge in self.edges
        ]
        edges += [GraphEdge(source=_START, target=activity, end_arrow="triangle") for activity in self.start_activities]
        edges += [GraphEdge(source=activity, target=_END, end_arrow="triangle") for activity in self.end_activities]
        return Graph(nodes=nodes, edges=edges, layout_config=DIRECTED_ELK_GRAPH_LAYOUT)


def build_df2(
    directly_follows: DFSnapshot, activities: Iterable[str], divergent: Iterable[tuple[str, str]]
) -> DF2Graph:
    """Builds the DF2 graph from directly-follows counts and divergent pairs.

    Args:
        directly_follows: Arc, start and end counts per object type.
        activities: All observed activities, Σ.
        divergent: The divergent pairs (activity, object type).
    """
    div: dict[str, set[str]] = {}
    for activity, object_type in divergent:
        div.setdefault(activity, set()).add(object_type)

    def diverges(activity: str, object_type: str) -> bool:
        return object_type in div.get(activity, ())

    edges: dict[tuple[str, str], tuple[int, set[str]]] = {}
    for (source, target, object_type), count in directly_follows.arcs.items():
        if count > 0 and not (diverges(source, object_type) and diverges(target, object_type)):
            total, types = edges.get((source, target), (0, set()))
            edges[(source, target)] = (total + count, types | {object_type})

    def endpoints(counts: dict[tuple[str, str], int]) -> list[str]:
        return sorted({a for (a, t), count in counts.items() if count > 0 and not diverges(a, t)})

    return DF2Graph(
        activities=sorted(activities),
        edges=[
            DF2Edge(source=source, target=target, count=count, object_types=sorted(types))
            for (source, target), (count, types) in sorted(edges.items())
        ],
        start_activities=endpoints(directly_follows.starts),
        end_activities=endpoints(directly_follows.ends),
        divergence=[DF2Divergence(activity=a, object_types=sorted(types)) for a, types in sorted(div.items())],
    )
