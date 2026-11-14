from ocelescope import DirectlyFollowsGraph
from ocelescope.visualization.default.graph import Graph


class StreamingDFG(DirectlyFollowsGraph):
    """Ocelescope's object-centric DFG, always shown in the ELK graph viewer instead of r4pm."""

    def visualize(self) -> Graph:
        return self._visualize_graph()
