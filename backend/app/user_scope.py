"""Seed user constants and helpers for per-user data scoping."""
from __future__ import annotations

import os

SEED_USER_ID = os.environ.get("DBSHERPA_SEED_USER_ID", "user_johndoe")
SEED_USERNAME = os.environ.get("DBSHERPA_SEED_USERNAME", "johndoe")
SEED_EMAIL = os.environ.get("DBSHERPA_SEED_EMAIL", "john.doe@dbsherpa.local")
SEED_NAME = os.environ.get("DBSHERPA_SEED_NAME", "John Doe")
SEED_PASSWORD = os.environ.get("DBSHERPA_SEED_PASSWORD", "password123")

ROLE_ADMIN = "admin"
ROLE_USER = "user"

# Coarse feature gates — absence of a row means enabled (opt-out).
USER_FEATURES: dict[str, str] = {
    "workflows": "Workflows & drafts",
    "run_history": "Run history",
    "data_sources": "Data sources",
    "skills": "Skills library",
    "node_palette": "Node palette & templates",
    "automations": "Automations",
}


def user_is_admin(user: dict | None) -> bool:
    """True when the user has the admin role."""
    if not user:
        return False
    return str(user.get("role") or ROLE_USER).strip().lower() == ROLE_ADMIN
