"""DF2 graphs (definitions.tex: def:df2)."""

from collections.abc import Iterable
from typing import Literal

from ocelescope import Resource
from ocelescope.visualization.default.graph import (
    DIRECTED_ELK_GRAPH_LAYOUT,
    EdgeStyle,
    Graph,
    GraphEdge,
    GraphNode,
    NodeStyle,
)
from ocelescope.visualization.util.color import generate_color_map
from pydantic import BaseModel, Field

from ocelescope_module_streaming.blocks import DFSnapshot


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


class DF2TypedArc(BaseModel):
    """A directly-follows relation of one object type, as in an OC-DFG.

    Attributes:
        source: The source activity, or None for a start activity.
        target: The target activity, or None for an end activity.
        object_type: The object type.
        count: The frequency.
        suppressed: Whether the DF2 graph drops it because of divergence: an arc whose type
            diverges on both activities, or a start or end activity whose type diverges on it.
    """

    source: str | None
    target: str | None
    object_type: str
    count: int
    suppressed: bool = False


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
        object_types: All observed object types.
        typed_arcs: The underlying OC-DFG, per object type, with the suppressed elements marked.
    """

    label = "DF2 Graph"
    description = "A divergence-free directly-follows graph"

    activities: list[str] = Field(default_factory=list)
    edges: list[DF2Edge] = Field(default_factory=list)
    start_activities: list[str] = Field(default_factory=list)
    end_activities: list[str] = Field(default_factory=list)
    divergence: list[DF2Divergence] = Field(default_factory=list)
    object_types: list[str] = Field(default_factory=list)
    typed_arcs: list[DF2TypedArc] = Field(default_factory=list)

    def divergent(self) -> dict[str, set[str]]:
        """Returns div(a) per activity."""
        return {entry.activity: set(entry.object_types) for entry in self.divergence}

    def visualize(self) -> Graph:
        """Draws the underlying OC-DFG; arcs the DF2 graph suppresses are dashed and grey.

        Activities show the object types they diverge for.
        """
        colors = generate_color_map(self.object_types, "custom")
        divergent = self.divergent()
        nodes = [
            GraphNode(
                id=activity,
                label=activity
                + (f"\n(div: {', '.join(sorted(divergent[activity]))})" if activity in divergent else ""),
                shape="rectangle",
                width=150,
                height=48 if activity in divergent else 40,
                color="#ffffff",
                border_color="#000000",
            )
            for activity in self.activities
        ]
        endpoints: tuple[tuple[str, Literal["triangle", "square"]], ...] = (("start", "triangle"), ("end", "square"))
        for arc_kind, symbol in endpoints:
            types = {
                arc.object_type
                for arc in self.typed_arcs
                if (arc.source if arc_kind == "start" else arc.target) is None
            }
            nodes += [
                GraphNode(
                    id=f"{arc_kind}_{object_type}",
                    label=object_type,
                    shape="circle",
                    width=40,
                    height=40,
                    color=colors[object_type],
                    border_color="#000000",
                    style=NodeStyle(inner_symbol=symbol),
                    label_pos="bottom",
                )
                for object_type in sorted(types)
            ]
        edges = [
            GraphEdge(
                source=arc.source or f"start_{arc.object_type}",
                target=arc.target or f"end_{arc.object_type}",
                end_arrow="triangle",
                color=SUPPRESSED_COLOR if arc.suppressed else colors[arc.object_type],
                style=EdgeStyle(dashed=arc.suppressed),
                label=str(arc.count),
            )
            for arc in self.typed_arcs
        ]
        return Graph(nodes=nodes, edges=edges, layout_config=DIRECTED_ELK_GRAPH_LAYOUT)


SUPPRESSED_COLOR = "#adb5bd"
"""The color of arcs the DF2 graph suppresses because of divergence."""


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

    typed_arcs = [
        *(
            DF2TypedArc(source=a, target=b, object_type=t, count=n, suppressed=diverges(a, t) and diverges(b, t))
            for (a, b, t), n in sorted(directly_follows.arcs.items())
            if n > 0
        ),
        *(
            DF2TypedArc(source=None, target=a, object_type=t, count=n, suppressed=diverges(a, t))
            for (a, t), n in sorted(directly_follows.starts.items())
            if n > 0
        ),
        *(
            DF2TypedArc(source=a, target=None, object_type=t, count=n, suppressed=diverges(a, t))
            for (a, t), n in sorted(directly_follows.ends.items())
            if n > 0
        ),
    ]
    return DF2Graph(
        object_types=sorted({arc.object_type for arc in typed_arcs}),
        typed_arcs=typed_arcs,
        activities=sorted(activities),
        edges=[
            DF2Edge(source=source, target=target, count=count, object_types=sorted(types))
            for (source, target), (count, types) in sorted(edges.items())
        ],
        start_activities=endpoints(directly_follows.starts),
        end_activities=endpoints(directly_follows.ends),
        divergence=[DF2Divergence(activity=a, object_types=sorted(types)) for a, types in sorted(div.items())],
    )
