import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class FactorMap:
    id: str
    project_factor_id: str
    project_factor_name: str
    project_factor_mode: str
    qlib_expression: str
    markethon_name: str
    created_at: str
    updated_at: str


class MarkethonFactorMapStore:
    """
    项目因子与 Markethon qlib 表达式映射的持久化存储（JSON 文件）。
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path = self.data_dir / "markethon_factor_maps.json"
        self._maps: dict[str, FactorMap] = {}
        self._load()

    def _load(self):
        if not self.storage_path.exists():
            return
        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                mapping = FactorMap(
                    id=item.get("id", str(uuid.uuid4())),
                    project_factor_id=item.get("project_factor_id", ""),
                    project_factor_name=item.get("project_factor_name", ""),
                    project_factor_mode=item.get("project_factor_mode", "formula"),
                    qlib_expression=item.get("qlib_expression", ""),
                    markethon_name=item.get("markethon_name", ""),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
                self._maps[mapping.id] = mapping
        except Exception:
            self._maps = {}

    def _save(self):
        records = [asdict(m) for m in self._maps.values()]
        with self.storage_path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def list(self) -> list[FactorMap]:
        return list(self._maps.values())

    def get(self, map_id: str) -> FactorMap | None:
        return self._maps.get(map_id)

    def get_by_project_factor_id(self, project_factor_id: str) -> FactorMap | None:
        for m in self._maps.values():
            if m.project_factor_id == project_factor_id:
                return m
        return None

    def create_or_update(
        self,
        project_factor_id: str,
        project_factor_name: str,
        project_factor_mode: str,
        qlib_expression: str,
        markethon_name: str,
    ) -> FactorMap:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get_by_project_factor_id(project_factor_id)
        if existing:
            existing.project_factor_name = project_factor_name
            existing.project_factor_mode = project_factor_mode
            existing.qlib_expression = qlib_expression
            existing.markethon_name = markethon_name
            existing.updated_at = now
            self._save()
            return existing

        mapping = FactorMap(
            id=str(uuid.uuid4()),
            project_factor_id=project_factor_id,
            project_factor_name=project_factor_name,
            project_factor_mode=project_factor_mode,
            qlib_expression=qlib_expression,
            markethon_name=markethon_name,
            created_at=now,
            updated_at=now,
        )
        self._maps[mapping.id] = mapping
        self._save()
        return mapping

    def update(self, map_id: str, **kwargs: Any) -> FactorMap | None:
        mapping = self._maps.get(map_id)
        if not mapping:
            return None

        for key, value in kwargs.items():
            if hasattr(mapping, key):
                setattr(mapping, key, value)

        mapping.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return mapping

    def delete(self, map_id: str) -> bool:
        if map_id not in self._maps:
            return False
        del self._maps[map_id]
        self._save()
        return True
