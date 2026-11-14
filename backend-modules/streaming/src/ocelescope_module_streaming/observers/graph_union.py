from typing import Any

from ocelescope.visualization.default.graph import Graph, GraphEdge, GraphNode

from ocelescope_module_streaming.algorithms import Finished, ItemProcessed, Observer, RunEvent, StreamingAlgorithm


class GraphUnion(Observer):
    """Collects every node and edge that the model's graph shows at any point of a run.

    Laid out once, the union gives every element a fixed place for a replay of the same run,
    including elements that are gone again by the end (e.g. evicted ones). Elements are matched
    by id, so the model's visualization must give them stable ids; the latest version wins.
    Models whose visualization is not a graph leave the union empty.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}
        self.layout_config: Any = None

    def notify(self, algorithm: StreamingAlgorithm[Any, Any], event: RunEvent) -> None:
        if isinstance(event, ItemProcessed | Finished):
            graph = algorithm.model().visualize()
            if isinstance(graph, Graph):
                self.nodes.update((node.id, node) for node in graph.nodes)
                self.edges.update((edge.id, edge) for edge in graph.edges)
                self.layout_config = graph.layout_config

    def graph(self) -> Graph | None:
        """The union as one graph; None if the model had no graph visualization."""
        if self.layout_config is None:
            return None
        return Graph(nodes=list(self.nodes.values()), edges=list(self.edges.values()), layout_config=self.layout_config)
