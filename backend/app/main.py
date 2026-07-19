from contextlib import asynccontextmanager
from pathlib import Path

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import backtest, data, factor, fib_levels, strategy, support_level
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
app.include_router(support_level.router)
app.include_router(fib_levels.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---- 生产模式：托管前端构建产物（SPA）----
# 路径可用 FRONTEND_DIST 环境变量覆盖，默认 backend/../frontend/dist
FRONTEND_DIST = Path(
    os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist")
)

if FRONTEND_DIST.is_dir():
    # 静态资源（js/css/图片等）
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA 回退：文件存在则返回文件，否则返回 index.html"""
        file = FRONTEND_DIST / full_path
        if full_path and file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    print(f"[warn] 前端构建目录不存在: {FRONTEND_DIST}，仅提供 API 服务")
