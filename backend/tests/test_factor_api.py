import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from app.main import app


def test_factor_api_crud():
    print("=" * 60)
    print("测试自定义因子 API CRUD")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # 通过环境变量或 monkeypatch 让 FactorStore 使用临时目录
        from app.api import factor as factor_module
        from app.data.factor_store import FactorStore

        original_store = factor_module._factor_store
        factor_module._factor_store = FactorStore(data_dir=tmpdir)

        try:
            client = TestClient(app)

            # 创建
            res = client.post("/api/factors", json={
                "name": "测试因子",
                "category": "测试",
                "description": "用于测试",
                "mode": "python",
                "code": "def factor(df):\n    return df['close']",
            })
            print(f"   创建状态: {res.status_code}")
            assert res.status_code == 200
            factor_id = res.json()["id"]

            # 列表
            res = client.get("/api/factors")
            print(f"   列表状态: {res.status_code}, 数量: {len(res.json()['factors'])}")
            assert res.status_code == 200
            assert len(res.json()["factors"]) == 1

            # 更新
            res = client.put(f"/api/factors/{factor_id}", json={
                "description": "已更新",
            })
            print(f"   更新状态: {res.status_code}")
            assert res.status_code == 200
            assert res.json()["description"] == "已更新"

            # 删除
            res = client.delete(f"/api/factors/{factor_id}")
            print(f"   删除状态: {res.status_code}")
            assert res.status_code == 200

            res = client.get("/api/factors")
            assert len(res.json()["factors"]) == 0

            # 测试统一因子库接口
            res = client.get("/api/factor/library")
            print(f"   统一因子库状态: {res.status_code}")
            assert res.status_code == 200
            data = res.json()
            assert "builtins" in data
            assert "custom" in data
            assert len(data["builtins"]) > 0
            assert len(data["custom"]) == 0

            # 测试单条查询（先创建一条）
            res = client.post("/api/factors", json={
                "name": "单条查询测试",
                "category": "测试",
                "description": "",
                "mode": "python",
                "code": "def factor(df): return df['close']",
            })
            fid = res.json()["id"]
            res = client.get(f"/api/factors/{fid}")
            print(f"   单条查询状态: {res.status_code}")
            assert res.status_code == 200
            assert res.json()["id"] == fid

            print("[OK] 自定义因子 API CRUD 测试通过")
        finally:
            factor_module._factor_store = original_store


if __name__ == "__main__":
    test_factor_api_crud()
