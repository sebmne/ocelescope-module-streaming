from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HelloResponse(BaseModel):
    message: str


@router.get("/hello", operation_id="hello", response_model=HelloResponse)
def hello() -> HelloResponse:
    return HelloResponse(message="Hello from the Streaming backend module")
