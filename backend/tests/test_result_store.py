import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.result_store import BacktestResultStore


def test_result_store():
    print("=" * 60)
    print("测试回测结果存储")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = BacktestResultStore(data_dir=tmpdir)

        result = {
            "id": "test-id",
            "symbol": "BTC_USDT",
            "summary": {"total_return": 0.1},
            "equity_curve": [{"timestamp": "2024-01-01", "equity": 10000}],
            "trades": [],
        }

        store.save("test-id", result)
        print("   保存成功")

        fetched = store.get("test-id")
        assert fetched is not None
        assert fetched["symbol"] == "BTC_USDT"
        print("   读取成功")

        listed = store.list()
        assert len(listed) == 1
        print("   列表成功")

        deleted = store.delete("test-id")
        assert deleted
        assert store.get("test-id") is None
        print("   删除成功")

    print("[OK] 回测结果存储测试通过")


if __name__ == "__main__":
    test_result_store()
