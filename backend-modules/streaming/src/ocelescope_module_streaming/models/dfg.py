from ocelescope import DirectlyFollowsGraph
from ocelescope.visualization.default.graph import Graph


class StreamingDFG(DirectlyFollowsGraph):
    """Ocelescope's object-centric DFG, always shown in the ELK graph viewer instead of r4pm.

    Edges get ids derived from object type, source and target instead of random ones, so the
    same edge keeps its id across the frames of a run.
    """

    def visualize(self) -> Graph:
        graph = self._visualize_graph()
        for edge, graph_edge in zip(self.edges, graph.edges, strict=True):  # built in the same order
            graph_edge.id = f"{edge.object_type}:{edge.source}->{edge.target}"
        return graph
