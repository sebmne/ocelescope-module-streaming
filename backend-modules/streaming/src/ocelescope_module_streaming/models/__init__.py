"""The module's model resources, one per file. Register new ones in `MODELS`."""

from ocelescope import Resource

from ocelescope_module_streaming.models.dfg import StreamingDFG
from ocelescope_module_streaming.models.petri_net import StreamingPetriNet
from ocelescope_module_streaming.models.totem import Totem, TotemEdge

MODELS: list[type[Resource]] = [StreamingDFG, StreamingPetriNet, Totem]

__all__ = ["MODELS", "StreamingDFG", "StreamingPetriNet", "Totem", "TotemEdge"]
