"""
Connector registry — routes catalog entries to the Oracle SQL connector.
"""
from __future__ import annotations

from connectors.catalog import DataSource, DataSourceRegistry, get_registry
from connectors.oracle_connector import OracleConnector

from connectors.base import ConnectorKind, TableBinding

_CONNECTOR = OracleConnector()


class ConnectorRegistry:
    """Dispatch row fetch to the Oracle connector declared on each catalog entry."""

    def __init__(self, catalog: DataSourceRegistry | None = None) -> None:
        self._catalog = catalog or get_registry()

    @property
    def catalog(self) -> DataSourceRegistry:
        return self._catalog

    def dataset_names(self) -> list[str]:
        return sorted(s.id for s in self._catalog.all())

    def get_rows(self, name: str) -> list[dict]:
        source = self._catalog.get(name)
        if source is None:
            return []
        binding = self._binding_for(source)
        return _CONNECTOR.fetch_rows(binding, raw_metadata=source.raw)

    def _binding_for(self, source: DataSource) -> TableBinding:
        if source.sources:
            return TableBinding(kind=ConnectorKind.ORACLE, ref=str(source.sources[0]))
        return TableBinding(kind=ConnectorKind.ORACLE, ref=f"oracle:DEMO.{source.id.upper().replace('.', '_')}")


_default = ConnectorRegistry()


def dataset_names() -> list[str]:
    return _default.dataset_names()


def get_rows(name: str) -> list[dict]:
    return _default.get_rows(name)
