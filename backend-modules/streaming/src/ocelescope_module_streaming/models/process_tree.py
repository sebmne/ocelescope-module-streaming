"""Object-centric process trees (definitions.tex: def:ocpt)."""

from collections.abc import Iterable
from typing import Literal

from ocelescope import Resource
from ocelescope.visualization.default.graph import ORDERED_TREE_LAYOUT, Graph, GraphEdge, GraphNode
from pydantic import BaseModel, Field

from ocelescope_module_streaming.models.df2 import DF2Graph

NodeKind = Literal["sequence", "xor", "parallel", "loop", "activity", "no_cut"]

OPERATOR_SYMBOLS: dict[str, str] = {"sequence": "→", "xor": "×", "parallel": "∧", "loop": "↺"}


class ProcessTreeNode(BaseModel):
    """A node of an object-centric process tree.

    Operators (`sequence`, `xor`, `parallel`, `loop`) have children. A leaf (`activity`) carries
    its activity and the object types it relates to (rel) and may exhibit convergence (con),
    divergence (div) and deficiency (deficient). A `no_cut` node holds the leaves of an
    activity set no cut applies to.
    """

    kind: NodeKind
    activity: str | None = None
    children: list["ProcessTreeNode"] = Field(default_factory=list)
    rel: list[str] = Field(default_factory=list)
    con: list[str] = Field(default_factory=list)
    div: list[str] = Field(default_factory=list)
    deficient: list[str] = Field(default_factory=list)

    def activities(self) -> list[str]:
        """The activities of all leaves below this node, left to right."""
        if self.kind == "activity":
            return [self.activity or ""]
        return [activity for child in self.children for activity in child.activities()]

    def notation(self) -> str:
        """A compact text form, e.g. ``sequence(a,xor(b,c))``."""
        if self.kind == "activity":
            return self.activity or ""
        return f"{self.kind}({','.join(child.notation() for child in self.children)})"


class OCPT(Resource):
    """An object-centric process tree.

    Attributes:
        root: The root node, or None for an empty tree.
        df2: The DF2 graph the tree was discovered from.
    """

    label = "Object-Centric Process Tree"
    description = "An object-centric process tree discovered from a DF2 graph"

    root: ProcessTreeNode | None = None
    df2: DF2Graph | None = None

    def visualize(self) -> Graph:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        def add(node: ProcessTreeNode) -> str:
            graph_node = _graph_node(node)
            nodes.append(graph_node)
            for child in node.children:
                edges.append(GraphEdge(source=graph_node.id, target=add(child)))
            return graph_node.id

        if self.root is not None:
            add(self.root)
        return Graph(nodes=nodes, edges=edges, layout_config=ORDERED_TREE_LAYOUT)


def _graph_node(node: ProcessTreeNode) -> GraphNode:
    if node.kind == "activity":
        lines = [node.activity or ""]
        for object_type in node.rel:
            marks = [
                name
                for name, types in (("con", node.con), ("div", node.div), ("def", node.deficient))
                if object_type in types
            ]
            lines.append(f"{object_type} [{', '.join(marks)}]" if marks else object_type)
        return GraphNode(
            label="\n".join(lines), shape="rectangle", width=160, height=24 + 16 * len(lines), color="#ffffff"
        )
    if node.kind == "no_cut":
        return GraphNode(label="no cut", shape="hexagon", width=70, height=40, color="#ffe3e3")
    return GraphNode(label=OPERATOR_SYMBOLS[node.kind], shape="circle", width=40, height=40, color="#ffffff")


def annotate(
    node: ProcessTreeNode,
    rel: Iterable[tuple[str, str]],
    con: Iterable[tuple[str, str]],
    div: Iterable[tuple[str, str]],
    deficient: Iterable[tuple[str, str]],
) -> ProcessTreeNode:
    """Returns a copy of the tree whose leaves carry their activity–type relations.

    Each argument is a set of (activity, object type) pairs.
    """
    relations = {
        name: _by_activity(pairs)
        for name, pairs in (("rel", rel), ("con", con), ("div", div), ("deficient", deficient))
    }

    def visit(current: ProcessTreeNode) -> ProcessTreeNode:
        if current.kind == "activity":
            activity = current.activity or ""
            return current.model_copy(
                update={name: sorted(types.get(activity, ())) for name, types in relations.items()}
            )
        return current.model_copy(update={"children": [visit(child) for child in current.children]})

    return visit(node)


def _by_activity(pairs: Iterable[tuple[str, str]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for activity, object_type in pairs:
        result.setdefault(activity, set()).add(object_type)
    return result
