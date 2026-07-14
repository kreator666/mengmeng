import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CustomFactor:
    id: str
    name: str
    category: str
    description: str
    mode: str
    code: str
    created_at: str
    updated_at: str


class FactorStore:
    """
    自定义因子持久化存储（JSON 文件）
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path = self.data_dir / "custom_factors.json"
        self._factors: dict[str, CustomFactor] = {}
        self._load()

    def _load(self):
        if not self.storage_path.exists():
            return
        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                # 兼容旧数据：缺失字段给默认值
                factor = CustomFactor(
                    id=item["id"],
                    name=item.get("name", ""),
                    category=item.get("category", "自定义"),
                    description=item.get("description", ""),
                    mode=item.get("mode", "python"),
                    code=item.get("code", ""),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
                self._factors[factor.id] = factor
        except Exception:
            self._factors = {}

    def _save(self):
        records = [asdict(f) for f in self._factors.values()]
        with self.storage_path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def list(self) -> list[CustomFactor]:
        return list(self._factors.values())

    def get(self, factor_id: str) -> CustomFactor | None:
        return self._factors.get(factor_id)

    def create(
        self,
        name: str,
        category: str,
        description: str,
        mode: str,
        code: str,
    ) -> CustomFactor:
        now = datetime.now(timezone.utc).isoformat()
        factor = CustomFactor(
            id=str(uuid.uuid4()),
            name=name,
            category=category,
            description=description,
            mode=mode,
            code=code,
            created_at=now,
            updated_at=now,
        )
        self._factors[factor.id] = factor
        self._save()
        return factor

    def update(self, factor_id: str, **kwargs: Any) -> CustomFactor | None:
        factor = self._factors.get(factor_id)
        if not factor:
            return None

        for key, value in kwargs.items():
            if hasattr(factor, key):
                setattr(factor, key, value)

        factor.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return factor

    def delete(self, factor_id: str) -> bool:
        if factor_id not in self._factors:
            return False
        del self._factors[factor_id]
        self._save()
        return True
