from __future__ import annotations

from generation.harness.subagent_permissions import derive_subagent_permissions


def test_parent_denies_are_always_inherited() -> None:
    parent = {"read": True, "edit": False, "shell": True}
    child = {"read": True, "edit": True, "shell": True}
    merged = derive_subagent_permissions(parent, child, allow_task_todo=False)
    assert merged["edit"] is False
    assert merged["read"] is True


def test_task_todo_denied_by_default() -> None:
    parent = {"read": True, "task": True, "todo": True}
    merged = derive_subagent_permissions(parent, {"task": True, "todo": True})
    assert merged["task"] is False
    assert merged["todo"] is False


def test_task_todo_allowed_only_when_explicit() -> None:
    parent = {"read": True, "task": True, "todo": True}
    merged = derive_subagent_permissions(
        parent,
        {"task": True, "todo": True},
        allow_task_todo=True,
    )
    assert merged["task"] is True
    assert merged["todo"] is True


def test_external_directory_restrictions_preserved() -> None:
    parent = {"read": True, "external_directory": False}
    merged = derive_subagent_permissions(parent, {"external_directory": True})
    assert merged["external_directory"] is False
