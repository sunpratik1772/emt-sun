"""node_type_ids constants match registered NODE_SPECS keys."""
from __future__ import annotations

import engine.node_type_ids as nti
from engine.registry import NODE_SPECS


def test_all_node_type_ids_in_registry() -> None:
    for name in nti.__all__:
        tid = getattr(nti, name)
        assert tid in NODE_SPECS, f"{tid!r} missing from NODE_SPECS"
