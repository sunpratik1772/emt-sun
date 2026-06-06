"""
Declarative catalog — parses ``metadata/*.yaml`` into typed schema objects.

Column schemas are the contract for validator, copilot prompts, and UI dropdowns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from connectors.base import ConnectorKind

METADATA_DIR = Path(__file__).parent / "metadata"


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type: str
    description: str = ""
    semantic: str | None = None
    optional: bool = False
    include_in_tab: bool = True

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "semantic": self.semantic,
            "optional": self.optional,
            "include_in_tab": self.include_in_tab,
        }


@dataclass(frozen=True)
class SourceSchema:
    name: str
    description: str = ""
    base_query: str = "*:*"
    columns: tuple[ColumnSpec, ...] = ()

    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "base_query": self.base_query,
            "columns": [c.to_json() for c in self.columns],
        }


@dataclass(frozen=True)
class DataSource:
    id: str
    description: str
    connector: ConnectorKind
    sources: tuple[str, ...]
    columns: tuple[ColumnSpec, ...]
    source_schemas: dict[str, SourceSchema] = field(default_factory=dict)
    raw: dict = field(default_factory=dict, repr=False)

    def column(self, name: str) -> ColumnSpec | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def source_schema(self, source: str | None) -> SourceSchema | None:
        if not source:
            return None
        return self.source_schemas.get(source)

    def column_names(self, source: str | None = None) -> tuple[str, ...]:
        schema = self.source_schema(source)
        if schema is not None:
            return schema.column_names()
        return tuple(c.name for c in self.columns)

    def semantic_map(self, source: str | None = None) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        columns = self.source_schema(source).columns if self.source_schema(source) else self.columns
        for c in columns:
            if c.semantic:
                result.setdefault(c.semantic, []).append(c.name)
        return result

    def resolve_field(self, name: str, source: str | None = None) -> str | None:
        if not name:
            return None
        if name in self.column_names(source):
            return name
        sm = self.semantic_map(source)
        if name in sm and sm[name]:
            return sm[name][0]
        return None

    def base_query(self, source: str | None = None) -> str:
        schema = self.source_schema(source)
        return schema.base_query if schema is not None else "*:*"

    def schema_hint(self) -> str:
        src_list = ", ".join(self.sources) if self.sources else self.id
        lines = [f"**{self.id}** ({src_list}) — {self.description}"]
        for c in self.columns:
            sem = f"  [semantic: {c.semantic}]" if c.semantic else ""
            opt = "  (optional)" if c.optional else ""
            lines.append(f"  - `{c.name}` ({c.type}){sem}{opt}")
        if self.source_schemas:
            lines.append("  Concrete sources:")
            for source_name, source_schema in self.source_schemas.items():
                lines.append(
                    f"    - `{source_name}` base_query=`{source_schema.base_query}`"
                )
                for c in source_schema.columns:
                    sem = f" [semantic: {c.semantic}]" if c.semantic else ""
                    opt = " (optional)" if c.optional else ""
                    lines.append(f"      - `{c.name}` ({c.type}){sem}{opt}")
        return "\n".join(lines)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "connector": self.connector.value,
            "sources": list(self.sources),
            "columns": [c.to_json() for c in self.columns],
            "source_schemas": {
                name: schema.to_json()
                for name, schema in self.source_schemas.items()
            },
        }


class DataSourceRegistry:
    """Immutable-after-load catalog loaded from metadata YAML files."""

    def __init__(self, sources: Iterable[DataSource]) -> None:
        self._by_id: dict[str, DataSource] = {s.id: s for s in sources}

    def get(self, source_id: str) -> DataSource | None:
        base_id, _ = split_source_ref(source_id)
        return self._by_id.get(base_id)

    def resolve_field(self, source_ref: str, field_name: str) -> str | None:
        source_id, source_name = split_source_ref(source_ref)
        ds = self.get(source_id)
        if ds is None:
            return None
        return ds.resolve_field(field_name, source_name)

    def column_names(self, source_ref: str) -> tuple[str, ...]:
        source_id, source_name = split_source_ref(source_ref)
        ds = self.get(source_id)
        if ds is None:
            return ()
        return ds.column_names(source_name)

    def all(self) -> tuple[DataSource, ...]:
        return tuple(self._by_id.values())

    def schema_hints_for_prompt(self) -> str:
        sections = "\n\n".join(s.schema_hint() for s in self.all())
        return (
            "Use ONLY the exact column names listed below. "
            "Semantic tags describe meaning — the column name is what you write "
            "in `field_bindings`, highlight `condition`, and any config that "
            "references a column. Never invent aliases.\n\n"
            + sections
        )

    def to_json(self) -> dict:
        return {"sources": [s.to_json() for s in self.all()]}


def split_source_ref(source_ref: str) -> tuple[str, str | None]:
    if ":" not in source_ref:
        return source_ref, None
    source_id, source_name = source_ref.split(":", 1)
    return source_id, source_name or None


def _parse_column(raw: dict) -> ColumnSpec:
    return ColumnSpec(
        name=raw["name"],
        type=raw.get("type", "string"),
        description=raw.get("description", ""),
        semantic=raw.get("semantic"),
        optional=bool(raw.get("optional", False)),
        include_in_tab=bool(raw.get("include_in_tab", True)),
    )


def _parse_source_schema(name: str, raw: dict) -> SourceSchema:
    return SourceSchema(
        name=name,
        description=raw.get("description", ""),
        base_query=raw.get("base_query", "*:*"),
        columns=tuple(_parse_column(c) for c in raw.get("columns", [])),
    )


def _union_columns(source_schemas: dict[str, SourceSchema], fallback: list[ColumnSpec]) -> tuple[ColumnSpec, ...]:
    if not source_schemas:
        return tuple(fallback)
    by_name: dict[str, ColumnSpec] = {}
    for schema in source_schemas.values():
        for column in schema.columns:
            by_name.setdefault(column.name, column)
    for column in fallback:
        by_name.setdefault(column.name, column)
    return tuple(by_name.values())


def _infer_connector(raw: dict, sources: tuple[str, ...]) -> ConnectorKind:
    explicit = raw.get("connector")
    if explicit:
        return ConnectorKind(str(explicit))
    for src in sources:
        if isinstance(src, str) and src.startswith("oracle:"):
            return ConnectorKind.ORACLE
    return ConnectorKind.ORACLE


def _parse_source(path: Path) -> DataSource:
    raw = yaml.safe_load(path.read_text()) or {}
    source_schemas = {
        name: _parse_source_schema(name, schema)
        for name, schema in (raw.get("source_schemas") or {}).items()
    }
    fallback_columns = [_parse_column(c) for c in raw.get("columns", [])]
    sources = tuple(raw.get("sources", []) or source_schemas.keys())
    return DataSource(
        id=raw["id"],
        description=raw.get("description", ""),
        connector=_infer_connector(raw, sources),
        sources=sources,
        columns=_union_columns(source_schemas, fallback_columns),
        source_schemas=source_schemas,
        raw=raw,
    )


def _load_all() -> DataSourceRegistry:
    sources: list[DataSource] = []
    if METADATA_DIR.is_dir():
        for path in sorted(METADATA_DIR.glob("*.yaml")):
            sources.append(_parse_source(path))
    return DataSourceRegistry(sources)


_REGISTRY: DataSourceRegistry = _load_all()


def get_registry() -> DataSourceRegistry:
    return _REGISTRY
