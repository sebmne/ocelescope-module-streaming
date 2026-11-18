from ocelescope import PetriNet
from ocelescope.visualization.default.graph import Graph


class StreamingPetriNet(PetriNet):
    """Ocelescope's object-centric Petri net, always shown in the ELK graph viewer."""

    def visualize(self) -> Graph:
        return self._visualize_graph()
