from fastapi import APIRouter

from ocelescope_module_streaming.algorithms import ALGORITHMS
from ocelescope_module_streaming.api.schemas import AlgorithmInfo, BufferInfo, HeuristicInfo
from ocelescope_module_streaming.framework import BufferAlgorithm
from ocelescope_module_streaming.heuristics import GENERAL, HEURISTICS

router = APIRouter(tags=["algorithms"])


@router.get("/algorithms", operation_id="listAlgorithms")
def list_algorithms() -> list[AlgorithmInfo]:
    return [
        AlgorithmInfo(
            key=key,
            label=cls.label,
            config_schema=cls.config_model.model_json_schema(),
            buffers=[
                BufferInfo(key=spec.key, label=spec.label, sink=spec.sink, heuristics=[*GENERAL, *spec.heuristics])
                for spec in (cls.buffer_specs if issubclass(cls, BufferAlgorithm) else ())
            ],
        )
        for key, cls in ALGORITHMS.items()
    ]


@router.get("/heuristics", operation_id="listHeuristics")
def list_heuristics() -> list[HeuristicInfo]:
    return [
        HeuristicInfo(key=key, label=cls.label, parameters_schema=cls.parameters_model.model_json_schema())
        for key, cls in HEURISTICS.items()
    ]
