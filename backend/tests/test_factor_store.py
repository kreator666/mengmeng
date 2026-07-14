import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.factor_store import FactorStore


def test_factor_crud():
    print("=" * 60)
    print("测试自定义因子存储 CRUD")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = FactorStore(data_dir=tmpdir)

        # 创建
        f1 = store.create(
            name="恐慌抄底",
            category="反转",
            description="连续暴跌后的抄底信号",
            mode="python",
            code="def factor(df):\n    return df['close']",
        )
        print(f"   创建因子: {f1.name} ({f1.id})")
        assert f1.name == "恐慌抄底"
        assert f1.category == "反转"

        # 列表
        factors = store.list()
        print(f"   列表数量: {len(factors)}")
        assert len(factors) == 1

        # 获取
        fetched = store.get(f1.id)
        assert fetched is not None
        assert fetched.name == "恐慌抄底"

        # 更新
        updated = store.update(f1.id, description="更新后的描述")
        assert updated is not None
        assert updated.description == "更新后的描述"

        # 删除
        deleted = store.delete(f1.id)
        assert deleted is True
        assert len(store.list()) == 0

        # 删除不存在的
        deleted = store.delete(f1.id)
        assert deleted is False

    print("[OK] 自定义因子存储 CRUD 测试通过")


if __name__ == "__main__":
    test_factor_crud()
