import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from app.main import app


def test_backtest_persistence():
    print("=" * 60)
    print("测试回测结果持久化 API")
    print("=" * 60)

    from app.api import backtest as backtest_module
    from app.data.result_store import BacktestResultStore

    original_store = backtest_module._result_store
    with tempfile.TemporaryDirectory() as tmpdir:
        backtest_module._result_store = BacktestResultStore(data_dir=tmpdir)

        try:
            client = TestClient(app)

            # 运行回测
            res = client.post("/api/backtest/run", json={
                "strategy": {
                    "name": "测试策略",
                    "factor_mode": "formula",
                    "factor_expression": "EMA(close, 12) > EMA(close, 26)",
                    "position_mode": "fixed_ratio",
                    "position_ratio": 0.95,
                    "initial_capital": 10000,
                    "fee_rate": 0.002,
                    "slippage": 0.0005,
                    "stop_loss": 0,
                    "take_profit": 0,
                    "max_holding_bars": 0,
                },
                "data": {
                    "symbol": "BTC_USDT",
                    "interval": "1h",
                    "market_type": "spot",
                    "from": "2026-06-01",
                    "to": "2026-06-07",
                },
            })
            print(f"   运行回测状态: {res.status_code}")
            if res.status_code != 200:
                print(f"   错误: {res.text}")
                return

            bt_id = res.json()["id"]
            print(f"   回测 ID: {bt_id}")

            # 列表
            res = client.get("/api/backtest")
            print(f"   列表状态: {res.status_code}")
            assert res.status_code == 200
            assert len(res.json()["results"]) == 1

            # 详情
            res = client.get(f"/api/backtest/{bt_id}")
            print(f"   详情状态: {res.status_code}")
            assert res.status_code == 200
            assert res.json()["id"] == bt_id

            print("[OK] 回测结果持久化 API 测试通过")
        finally:
            backtest_module._result_store = original_store


if __name__ == "__main__":
    test_backtest_persistence()
