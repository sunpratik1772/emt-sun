from __future__ import annotations

from typing import Mapping


def derive_subagent_permissions(
    parent_permissions: Mapping[str, bool],
    requested_permissions: Mapping[str, bool] | None = None,
    *,
    allow_task_todo: bool = False,
) -> dict[str, bool]:
    requested = dict(requested_permissions or {})
    merged: dict[str, bool] = {}

    keys = set(parent_permissions.keys()) | set(requested.keys())
    for key in keys:
        parent_allowed = bool(parent_permissions.get(key, False))
        child_requested = bool(requested.get(key, parent_allowed))

        # Parent denies are hard constraints and must propagate.
        if not parent_allowed:
            merged[key] = False
            continue

        merged[key] = child_requested

    # Preserve external-directory restrictions for subagents.
    for restricted_key in ("external_directory", "external_directories"):
        if restricted_key in parent_permissions and not parent_permissions.get(restricted_key, True):
            merged[restricted_key] = False

    # task/todo are denied by default unless explicitly allowed.
    if not allow_task_todo:
        merged["task"] = False
        merged["todo"] = False
    else:
        merged["task"] = bool(parent_permissions.get("task", False) and requested.get("task", True))
        merged["todo"] = bool(parent_permissions.get("todo", False) and requested.get("todo", True))

    return merged
