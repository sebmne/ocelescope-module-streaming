from fastapi import APIRouter

from ocelescope_module_streaming.api.schemas import AlgorithmInfo, Catalog, HeuristicInfo
from ocelescope_module_streaming.catalog import algorithms, heuristics

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", operation_id="getCatalog", summary="List available algorithms and heuristics")
def get_catalog() -> Catalog:
    return Catalog(
        algorithms=[AlgorithmInfo.from_spec(spec) for spec in algorithms],
        heuristics=[HeuristicInfo.from_spec(spec) for spec in heuristics],
    )
