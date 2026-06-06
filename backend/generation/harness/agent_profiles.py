from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ProfileMode = Literal["primary", "subagent"]


@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    model_hint: str
    permissions: dict[str, bool]
    max_steps: int
    mode: ProfileMode


_PROFILES: dict[str, AgentProfile] = {
    "build": AgentProfile(
        name="build",
        description="Default full-access profile for workflow implementation.",
        model_hint="high-capability",
        permissions={
            "read": True,
            "edit": True,
            "shell": True,
            "network": True,
            "task": True,
            "todo": True,
        },
        max_steps=6,
        mode="primary",
    ),
    "plan": AgentProfile(
        name="plan",
        description="Read-only planning profile for safe analysis.",
        model_hint="fast-reasoning",
        permissions={
            "read": True,
            "edit": False,
            "shell": False,
            "network": False,
            "task": False,
            "todo": False,
        },
        max_steps=4,
        mode="primary",
    ),
    "general": AgentProfile(
        name="general",
        description="General-purpose multi-step subagent profile.",
        model_hint="balanced",
        permissions={
            "read": True,
            "edit": True,
            "shell": True,
            "network": True,
            "task": False,
            "todo": False,
        },
        max_steps=5,
        mode="subagent",
    ),
    "explore": AgentProfile(
        name="explore",
        description="Read-only subagent profile for fast codebase discovery.",
        model_hint="fast",
        permissions={
            "read": True,
            "edit": False,
            "shell": False,
            "network": False,
            "task": False,
            "todo": False,
        },
        max_steps=4,
        mode="subagent",
    ),
}


def get_profile(name: str) -> AgentProfile:
    return _PROFILES.get(name, _PROFILES["build"])


def resolve_primary_profile(scenario: str) -> AgentProfile:
    explicit = (os.environ.get("HARNESS_AGENT_PROFILE") or "").strip().lower()
    if explicit in _PROFILES and _PROFILES[explicit].mode == "primary":
        return _PROFILES[explicit]

    text = (scenario or "").lower()
    if any(k in text for k in ("read-only", "read only", "analysis only", "plan only")):
        return _PROFILES["plan"]
    return _PROFILES["build"]


def resolve_max_steps(profile: AgentProfile) -> int:
    raw = (os.environ.get("HARNESS_MAX_STEPS") or "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return max(1, int(profile.max_steps))
