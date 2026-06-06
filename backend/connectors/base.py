"""
Connector base types — shared protocol for every data backend.

Every dataset uses the Oracle SQL connector (live ``ORACLE_DSN`` or demo fixture).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConnectorKind(str, Enum):
    """Physical storage backend for a catalog entry."""

    ORACLE = "oracle"


@dataclass(frozen=True)
class TableBinding:
    """Maps a catalog entry to physical storage."""

    kind: ConnectorKind
    ref: str  # e.g. "oracle:DEMO.ORDERS", "oracle:SURVEILLANCE.HS_TRADES"


@dataclass(frozen=True)
class OnboardingTemplate:
    """Copy-paste artifact for onboarding one table/collection."""

    connector_kind: ConnectorKind
    yaml_template: str
    readme: str


class BaseConnector(ABC):
    """Fetch rows from one backend type."""

    kind: ConnectorKind

    @abstractmethod
    def fetch_rows(
        self,
        binding: TableBinding,
        *,
        raw_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return all rows for the bound table (demo / best-effort)."""

    @classmethod
    @abstractmethod
    def onboarding_template(cls) -> OnboardingTemplate:
        """YAML + instructions for onboarding a new table of this kind."""
