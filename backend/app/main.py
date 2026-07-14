from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import backtest, data, factor, strategy
from app.api.factor import custom_factor_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Quant Backtest System",
    description="基于 Gate.io API 的加密货币量化回测系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(backtest.router)
app.include_router(factor.router)
app.include_router(custom_factor_router)
app.include_router(strategy.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
