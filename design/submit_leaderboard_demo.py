"""天梯成绩提交 Demo（factor-eval v4 正式口径）。

环境变量（任选一种登录方式）：
  1. 已有 token：FACTOR_EVAL_API_URL + FACTOR_EVAL_TOKEN
  2. 用户名密码：FACTOR_EVAL_API_URL + FACTOR_EVAL_USER + FACTOR_EVAL_PASSWORD

示例：
  export FACTOR_EVAL_API_URL=https://127.0.0.1:8601
  export FACTOR_EVAL_USER=demo
  export FACTOR_EVAL_PASSWORD=123456
  python examples/submit_leaderboard_demo.py

说明：
  - 本脚本会先加载官方 IM 股票池（天梯固定五年区间 2021-08-21 ~ 2026-08-20）。
  - 然后注册两个自定义因子（可选，仅作示例）。
  - 最后调用 POST /scores/submit 提交一条滚动回测成绩。
  - v4 正式提交会强制使用固定参数（train/test/step、quantiles、rebalance、benchmark 等），
    服务端会把不合法的参数直接 400 拒绝，因此这里显式写死固定值。
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# 配置：从环境变量读取
# ---------------------------------------------------------------------------
API_URL = os.environ.get("FACTOR_EVAL_API_URL", "https://127.0.0.1:8601").rstrip("/")
TOKEN = os.environ.get("FACTOR_EVAL_TOKEN")
USERNAME = os.environ.get("FACTOR_EVAL_USER")
PASSWORD = os.environ.get("FACTOR_EVAL_PASSWORD")

# 自签证书场景下关闭 SSL 校验（生产环境请使用受信任证书并删除这行逻辑）
SSL_CONTEXT = ssl._create_unverified_context()

# ---------------------------------------------------------------------------
# 从 factor-eval v4 代码中提取的天梯官方 IM 股票池常量
# ---------------------------------------------------------------------------
OFFICIAL_UNIVERSE_CODE = "IM"
OFFICIAL_UNIVERSE_ID = os.environ.get(
    "FACTOR_EVAL_OFFICIAL_UNIVERSE_ID", "official_im_constituents_v4"
)
FIXED_START = "2021-08-21"
FIXED_END = "2026-08-20"
TRAIN_MONTHS = 12
# 训练预热起点 = FIXED_START 往前推 12 个月，即 2020-08-21
TRAINING_WARMUP_START = "2020-08-21"

# 中证 1000 成分表下载地址（与 factor_eval/universe.py 一致）
IM_CONS_URL = (
    "https://oss-ch.csindex.com.cn/static/html/csindex/public/"
    "uploads/file/autofile/cons/000852cons.xls"
)


# ---------------------------------------------------------------------------
# HTTP 请求工具
# ---------------------------------------------------------------------------
def request(method: str, path: str, payload: dict | None = None, timeout: int = 300) -> dict:
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} 失败 [{exc.code}]: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {path} 网络错误: {exc}") from exc


def login(username: str, password: str) -> str:
    """登录并返回 token；新用户在网页端首次登录时会自动注册。"""
    global TOKEN
    result = request("POST", "/auth/login", {"username": username, "password": password}, timeout=30)
    TOKEN = result["token"]
    print(f"已登录: {username}, token 前缀: {TOKEN[:8]}...")
    return TOKEN


# ---------------------------------------------------------------------------
# 各步骤封装
# ---------------------------------------------------------------------------
def _symbols_sha256(symbols: list[str]) -> str:
    """与 factor_eval/competition_policy.py 一致的 SHA-256 校验。"""
    normalized = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()


def build_official_im_manifest(symbols: list[str]) -> dict:
    """根据代码中的 v4 规则，构造官方 IM 股票池审计 manifest。"""
    normalized = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    return {
        "source": "official_universe",
        "universe": OFFICIAL_UNIVERSE_CODE,
        "official_universe_id": OFFICIAL_UNIVERSE_ID,
        "official_universe_code": OFFICIAL_UNIVERSE_CODE,
        "official_locked": True,
        "start": TRAINING_WARMUP_START,
        "end": FIXED_END,
        "score_start": FIXED_START,
        "score_end": FIXED_END,
        "symbol_count": len(normalized),
        "symbols_sha256": _symbols_sha256(normalized),
        "symbols": normalized,
    }


def load_official_data() -> dict:
    """加载天梯官方数据视图：IM 成分股 + 训练预热期 + 固定五年区间。"""
    payload = {
        "universe": "IM",                  # 官方股票池：IM = 中证 1000
        "start": TRAINING_WARMUP_START,    # 2020-08-21，覆盖训练预热期
        "end": FIXED_END,                  # 2026-08-20，天梯固定截止日
        "alpha360": False,
        "use_cache": True,
    }
    print("正在加载官方 IM 数据...")
    result = request("POST", "/data/load", payload, timeout=1800)

    # 从服务端获取实际加载的股票代码，并构造一份本地官方 manifest 用于展示/校验
    current = request("GET", "/data/current-symbols", timeout=60)
    loaded_symbols = list(current.get("symbols") or [])
    expected_manifest = build_official_im_manifest(loaded_symbols)
    server_manifest = result.get("data_manifest") or {}

    print(
        f"数据加载完成: 股票数={len(loaded_symbols)}, "
        f"区间={result.get('date_range')}"
    )
    print(
        f"官方锁定校验: official_locked={server_manifest.get('official_locked')}, "
        f"leaderboard_eligible={server_manifest.get('leaderboard_eligible')}, "
        f"official_universe_id={server_manifest.get('official_universe_id')}"
    )
    print(f"本地构造 manifest symbols_sha256: {expected_manifest['symbols_sha256']}")
    print(f"服务端 manifest symbols_sha256:   {server_manifest.get('symbols_sha256')}")
    if server_manifest.get("symbols_sha256") != expected_manifest["symbols_sha256"]:
        print("警告：服务端返回的 symbols_sha256 与本地计算不一致", file=sys.stderr)
    return result


def register_custom_factors(factors: dict[str, str]) -> dict:
    """批量注册自定义因子（qlib 表达式）。

    优先使用 /factors/define_bulk；服务端不支持时逐个回退到 /factors/define。
    """
    if not factors:
        return {}
    print(f"正在注册自定义因子: {list(factors.keys())}")
    try:
        result = request("POST", "/factors/define_bulk", {"factors": factors}, timeout=120)
        print(f"批量注册结果: {result}")
        return result
    except RuntimeError as exc:
        print(f"批量注册失败: {exc}，尝试逐个注册...")
        for name, expression in factors.items():
            request("POST", "/factors/define", {"name": name, "expression": expression}, timeout=60)
            print(f"  已注册: {name}")
        return {"registered": list(factors.keys())}


def submit_leaderboard_score(names: list[str], submission_key: str) -> dict:
    """调用 /scores/submit 提交一条天梯成绩。

    v4 正式提交参数已由服务端强制固定，这里显式传入，便于本地校验和留痕。
    """
    payload = {
        # 因子池（>=10 个；服务端会去重、转大写）
        "names": names,

        # v4 强制固定参数
        "train_months": 12,
        "test_months": 3,
        "step_months": 3,
        "long_short": True,
        "quantiles": 5,
        "rebalance_periods": 5,
        "benchmark": "IF",
        "long_exposure": 0.95,
        "short_exposure": 0.95,
        "futures_cost": 0.0002,
        "selection_method": "legacy",
        "min_abs_icir": 0.10,
        "min_abs_ic": 0.005,
        "corr_threshold": 0.75,
        "weight_shrinkage": 0.50,

        # 类别控制：正式提交不允许自定义 category_counts，保持 None 即可
        "category_counts": None,
        "uncategorized_count": len(names),

        # 成绩提交开关 / 幂等键
        "submit_score": True,
        "submission_key": submission_key,
    }
    print(f"正在提交成绩，submission_key={submission_key}...")
    return request("POST", "/scores/submit", payload, timeout=7200)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    # 1. 认证
    if not TOKEN:
        if not USERNAME or not PASSWORD:
            print(
                "错误：未提供 token。请设置 FACTOR_EVAL_TOKEN，"
                "或同时设置 FACTOR_EVAL_USER + FACTOR_EVAL_PASSWORD。",
                file=sys.stderr,
            )
            return 1
        login(USERNAME, PASSWORD)
    else:
        print(f"使用已有 token: {TOKEN[:8]}...")

    # 2. 加载数据
    load_official_data()

    # 3.（可选）注册自定义因子
    custom_factors = {
        "DEMO_MOM5": "$close/Ref($close,5)-1",
        "DEMO_VOLR20": "Mean($volume,20)/Mean($volume,60)",
    }
    register_custom_factors(custom_factors)

    # 4. 准备 >=10 个候选因子（自定义 + 内置 Alpha158）
    candidate_names = [
        *list(custom_factors.keys()),
        "KMID", "KLEN", "ROC5", "ROC20", "STD20", "VMA10", "RSV5", "RSV10",
    ]
    if len(candidate_names) < 10:
        print("候选因子不足 10 个", file=sys.stderr)
        return 1

    # 5. 提交成绩（幂等键：同一用户同一键只保存一条记录）
    submission_key = os.environ.get("SUBMISSION_KEY", "demo-v4-submit-001")
    result = submit_leaderboard_score(candidate_names, submission_key)

    # 6. 打印关键结果
    summary = {
        "standard_score": result.get("standard_score"),
        "submission": result.get("submission"),
        "submission_skipped": result.get("submission_skipped"),
        "windows_count": len(result.get("windows", [])),
        "stock_count": result.get("stock_count"),
        "metrics": result.get("metrics"),
    }
    print("\n提交结果摘要:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 如果有跳过原因，给出明确提示
    skipped = result.get("submission_skipped")
    if skipped:
        print(f"\n注意：成绩未进入天梯，原因: {skipped}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
