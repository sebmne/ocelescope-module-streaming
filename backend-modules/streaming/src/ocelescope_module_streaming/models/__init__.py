"""The module's model resources, one per file. Register new ones in `MODELS`."""

from ocelescope import Resource

from ocelescope_module_streaming.models.dfg import StreamingDFG

MODELS: list[type[Resource]] = [StreamingDFG]

__all__ = ["MODELS", "StreamingDFG"]
