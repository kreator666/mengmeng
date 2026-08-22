"""
Markethon 比赛系统 API 客户端（异步）。

封装 https://markethon.fit:19371 的 REST 接口，提供登录态自动维护、401 重试、
统一错误转译。配置优先从环境变量读取：
  MARKETHON_BASE_URL
  MARKETHON_USERNAME
  MARKETHON_PASSWORD
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

_MARKETHON_BASE_URL = os.environ.get("MARKETHON_BASE_URL", "https://markethon.fit:19371").rstrip("/")
_MARKETHON_USERNAME = os.environ.get("MARKETHON_USERNAME", "")
_MARKETHON_PASSWORD = os.environ.get("MARKETHON_PASSWORD", "")

DEFAULT_TIMEOUT = 180.0


def _parse_json_with_nan(text: str) -> Any:
    """
    解析 Markethon 响应中的 JSON。
    服务可能返回 NaN/Inf（净值序列中非法数值用 null 表示，但-metrics 中可能存在
    字符串百分比，这里先做兼容性解析）。
    """
    return json.loads(text)


class MarkethonError(Exception):
    """Markethon API 返回的业务错误。"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class MarkethonClient:
    """Markethon 比赛系统异步 HTTP 客户端。"""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = (base_url or _MARKETHON_BASE_URL).rstrip("/")
        self.username = username or _MARKETHON_USERNAME
        self.password = password or _MARKETHON_PASSWORD
        self.timeout = timeout
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> MarkethonClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def login(self, username: str | None = None, password: str | None = None) -> dict[str, Any]:
        """
        POST /auth/login。新用户名自动注册。
        显式传入的 username/password 会覆盖环境变量配置，并同步更新实例。
        """
        user = username or self.username
        pwd = password or self.password
        if not user or not pwd:
            raise MarkethonError(400, "缺少 Markethon 用户名或密码")

        resp = await self.client.post(
            "/auth/login",
            json={"username": user, "password": pwd},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        data = self._parse_response(resp)

        self.username = user
        self.password = pwd
        self._token = data.get("access_token") or data.get("token")
        expires_in = data.get("expires_in")
        if expires_in and isinstance(expires_in, (int, float)):
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        else:
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        return data

    def _parse_response(self, resp: httpx.Response) -> Any:
        text = resp.text
        try:
            data = _parse_json_with_nan(text) if text else {}
        except json.JSONDecodeError as e:
            raise MarkethonError(resp.status_code, f"非 JSON 响应: {text[:200]} ({e})")

        if resp.is_success:
            return data

        detail = data.get("detail") if isinstance(data, dict) else str(data)
        raise MarkethonError(resp.status_code, detail or f"请求失败: {resp.reason_phrase}")

    async def _ensure_token(self) -> None:
        """无 token 或 token 接近过期时重新登录。"""
        if self._token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at - timedelta(minutes=5):
                return
        await self.login()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        auth_required: bool = True,
        retry_401: bool = True,
        timeout: float | None = None,
    ) -> Any:
        if auth_required:
            await self._ensure_token()

        url = f"{self.base_url}{path}"
        client = self.client
        if timeout is not None and timeout != self.timeout:
            # 为单个请求创建临时客户端，避免污染连接池超时配置
            client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            )
        try:
            resp = await client.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._headers(),
            )
        except httpx.TimeoutException as e:
            raise MarkethonError(504, f"Markethon 请求超时: {e}")
        except httpx.RequestError as e:
            raise MarkethonError(502, f"Markethon 连接失败: {e}")
        finally:
            if timeout is not None and timeout != self.timeout and client is not self.client:
                await client.aclose()

        if resp.status_code == 401 and retry_401 and auth_required:
            await self.login()
            return await self._request(method, path, params, json, auth_required, retry_401=False, timeout=timeout)

        return self._parse_response(resp)

    # ------------------------------------------------------------------
    # 系统
    # ------------------------------------------------------------------

    async def get_health(self) -> dict[str, Any]:
        """GET /health（无需认证）"""
        return await self._request("GET", "/health", auth_required=False)

    async def get_status(self) -> dict[str, Any]:
        """GET /status"""
        return await self._request("GET", "/status")

    # ------------------------------------------------------------------
    # 数据
    # ------------------------------------------------------------------

    async def list_symbols(self, limit: int = 50) -> dict[str, Any]:
        """GET /data/symbols"""
        return await self._request("GET", "/data/symbols", params={"limit": limit})

    async def load_data(
        self,
        limit: int = 500,
        symbols: list[str] | None = None,
        universe: str | list[str] | None = None,
        start: str = "2021-08-21",
        end: str = "2026-08-20",
        alpha360: bool = False,
    ) -> dict[str, Any]:
        """POST /data/load"""
        payload: dict[str, Any] = {
            "limit": limit,
            "start": start,
            "end": end,
            "alpha360": alpha360,
        }
        if symbols is not None:
            payload["symbols"] = symbols
        if universe is not None:
            payload["universe"] = universe
        return await self._request("POST", "/data/load", json=payload)

    # ------------------------------------------------------------------
    # 因子
    # ------------------------------------------------------------------

    async def list_factors(self) -> dict[str, Any]:
        """GET /factors"""
        return await self._request("GET", "/factors")

    async def define_factor(self, name: str, expression: str) -> dict[str, Any]:
        """POST /factors/define"""
        return await self._request(
            "POST", "/factors/define", json={"name": name, "expression": expression}
        )

    async def evaluate_factors(
        self,
        names: list[str],
        periods: list[int] | None = None,
        quantiles: int = 5,
        top_n: int = 50,
    ) -> dict[str, Any]:
        """POST /factors/evaluate"""
        payload: dict[str, Any] = {
            "names": names,
            "quantiles": quantiles,
            "top_n": top_n,
        }
        if periods is not None:
            payload["periods"] = periods
        return await self._request("POST", "/factors/evaluate", json=payload)

    async def evaluate_all(
        self,
        factor_set: str = "alpha158",
        periods: list[int] | None = None,
        quantiles: int = 5,
        top_n: int = 50,
    ) -> dict[str, Any]:
        """POST /factors/evaluate_all"""
        payload: dict[str, Any] = {
            "factor_set": factor_set,
            "quantiles": quantiles,
            "top_n": top_n,
        }
        if periods is not None:
            payload["periods"] = periods
        return await self._request("POST", "/factors/evaluate_all", json=payload)

    async def evaluate_job(
        self,
        names: list[str] | None = None,
        factor_set: str = "alpha158",
        periods: list[int] | None = None,
        quantiles: int = 5,
    ) -> dict[str, Any]:
        """POST /jobs/evaluate"""
        payload: dict[str, Any] = {
            "names": names,
            "factor_set": factor_set,
            "quantiles": quantiles,
        }
        if periods is not None:
            payload["periods"] = periods
        return await self._request("POST", "/jobs/evaluate", json=payload)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        """GET /jobs/{job_id}"""
        return await self._request("GET", f"/jobs/{job_id}")

    # ------------------------------------------------------------------
    # 回测
    # ------------------------------------------------------------------

    async def backtest_quantile(
        self,
        names: list[str],
        weights: dict[str, float] | None = None,
        long_short: bool = True,
        periods: int = 5,
        quantiles: int = 5,
        benchmark: str | None = None,
    ) -> dict[str, Any]:
        """POST /backtest/quantile"""
        payload: dict[str, Any] = {
            "names": names,
            "long_short": long_short,
            "periods": periods,
            "quantiles": quantiles,
        }
        if weights is not None:
            payload["weights"] = weights
        if benchmark is not None:
            payload["benchmark"] = benchmark
        return await self._request("POST", "/backtest/quantile", json=payload)

    async def walk_forward(
        self,
        names: list[str],
        train_months: int = 12,
        test_months: int = 3,
        step_months: int = 3,
        long_short: bool = True,
        quantiles: int = 5,
        rebalance_periods: int = 5,
        category_counts: dict[str, int] | None = None,
        uncategorized_count: int = 5,
        selection_method: str = "legacy",
        min_abs_icir: float = 0.10,
        min_abs_ic: float = 0.005,
        corr_threshold: float = 0.75,
        weight_shrinkage: float = 0.50,
        benchmark: str | None = None,
        submit_score: bool = False,
    ) -> dict[str, Any]:
        """POST /backtest/walk_forward"""
        payload: dict[str, Any] = {
            "names": names,
            "train_months": train_months,
            "test_months": test_months,
            "step_months": step_months,
            "long_short": long_short,
            "quantiles": quantiles,
            "rebalance_periods": rebalance_periods,
            "uncategorized_count": uncategorized_count,
            "selection_method": selection_method,
            "min_abs_icir": min_abs_icir,
            "min_abs_ic": min_abs_ic,
            "corr_threshold": corr_threshold,
            "weight_shrinkage": weight_shrinkage,
            "submit_score": submit_score,
        }
        if category_counts is not None:
            payload["category_counts"] = category_counts
        if benchmark is not None:
            payload["benchmark"] = benchmark
        return await self._request("POST", "/backtest/walk_forward", json=payload)

    # ------------------------------------------------------------------
    # 选股
    # ------------------------------------------------------------------

    async def select_stocks(
        self,
        names: list[str],
        weights: dict[str, float] | None = None,
        top_n: int = 20,
        date: str | None = None,
        min_amount_cny: float = 0.0,
        min_listed_days: int = 0,
    ) -> dict[str, Any]:
        """POST /selection"""
        payload: dict[str, Any] = {
            "names": names,
            "top_n": top_n,
            "min_amount_cny": min_amount_cny,
            "min_listed_days": min_listed_days,
        }
        if weights is not None:
            payload["weights"] = weights
        if date is not None:
            payload["date"] = date
        return await self._request("POST", "/selection", json=payload)

    # ------------------------------------------------------------------
    # 数据 / 天梯正式提交
    # ------------------------------------------------------------------

    async def get_current_symbols(self) -> dict[str, Any]:
        """GET /data/current-symbols"""
        return await self._request("GET", "/data/current-symbols")

    async def submit_leaderboard_score(
        self,
        names: list[str],
        submission_key: str,
        train_months: int = 12,
        test_months: int = 3,
        step_months: int = 3,
        long_short: bool = True,
        quantiles: int = 5,
        rebalance_periods: int = 5,
        benchmark: str = "IF",
        long_exposure: float = 0.95,
        short_exposure: float = 0.95,
        futures_cost: float = 0.0002,
        selection_method: str = "legacy",
        min_abs_icir: float = 0.10,
        min_abs_ic: float = 0.005,
        corr_threshold: float = 0.75,
        weight_shrinkage: float = 0.50,
        category_counts: dict[str, int] | None = None,
        uncategorized_count: int | None = None,
        submit_score: bool = True,
    ) -> dict[str, Any]:
        """POST /scores/submit"""
        payload: dict[str, Any] = {
            "names": names,
            "train_months": train_months,
            "test_months": test_months,
            "step_months": step_months,
            "long_short": long_short,
            "quantiles": quantiles,
            "rebalance_periods": rebalance_periods,
            "benchmark": benchmark,
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
            "futures_cost": futures_cost,
            "selection_method": selection_method,
            "min_abs_icir": min_abs_icir,
            "min_abs_ic": min_abs_ic,
            "corr_threshold": corr_threshold,
            "weight_shrinkage": weight_shrinkage,
            "category_counts": category_counts,
            "uncategorized_count": uncategorized_count if uncategorized_count is not None else len(names),
            "submit_score": submit_score,
            "submission_key": submission_key,
        }
        return await self._request("POST", "/scores/submit", json=payload, timeout=7200.0)


# ----------------------------------------------------------------------
# 模块级单例，供路由层复用
# ----------------------------------------------------------------------

_markethon_client: MarkethonClient | None = None


def get_markethon_client() -> MarkethonClient:
    """获取全局 Markethon 客户端单例。"""
    global _markethon_client
    if _markethon_client is None:
        _markethon_client = MarkethonClient()
    return _markethon_client


def reset_markethon_client() -> None:
    """重置全局客户端（主要用于测试）。"""
    global _markethon_client
    _markethon_client = None
