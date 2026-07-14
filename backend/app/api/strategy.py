from fastapi import APIRouter

router = APIRouter(prefix="/api/strategies", tags=["strategy"])


@router.get("")
async def list_strategies():
    return {"strategies": []}


@router.post("")
async def create_strategy():
    return {"message": "create strategy placeholder"}
