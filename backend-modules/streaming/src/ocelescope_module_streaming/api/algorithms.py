from fastapi import APIRouter

from ocelescope_module_streaming.algorithms import ALGORITHMS
from ocelescope_module_streaming.api.schemas import AlgorithmInfo

router = APIRouter(prefix="/algorithms", tags=["algorithms"])


@router.get("", operation_id="listAlgorithms")
def list_algorithms() -> list[AlgorithmInfo]:
    return [
        AlgorithmInfo(key=key, label=cls.label, config_schema=cls.config_model.model_json_schema())
        for key, cls in ALGORITHMS.items()
    ]
