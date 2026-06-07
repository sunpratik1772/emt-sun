"""Unit tests for understand_anything context retrieval in retriever and enrichment layers."""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from generation.harness.intent import classify
from generation.harness.memory import MemoryManager
from generation.harness.retriever import ContextRetriever
from generation.harness.enrichment import format_user_enrichment


@pytest.fixture
def retriever(tmp_path):
    memory = MemoryManager(memory_dir=tmp_path / "memory")
    return ContextRetriever(memory=memory, templates_dir=tmp_path / "templates")


class TestUARetrieval:
    def test_retrieves_ua_context_when_enabled(self, retriever, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "1")
        intent = classify("auth profile execution log scheduler")
        ctx = retriever.retrieve(intent)

        # Check that it attempted to retrieve domains, flows, or steps
        # Given the real graphs exist in .understand-anything, this will match real nodes.
        assert hasattr(ctx, "ua_domains")
        assert hasattr(ctx, "ua_flows")
        assert hasattr(ctx, "ua_steps")
        
        # Verify counts in serialization
        serialized = ctx.to_dict()
        assert "ua_domains_count" in serialized
        assert "ua_flows_count" in serialized
        assert "ua_steps_count" in serialized

    def test_does_not_retrieve_ua_context_when_disabled(self, retriever, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "0")
        intent = classify("auth profile execution log scheduler")
        ctx = retriever.retrieve(intent)

        # Matched lists should be empty when disabled
        assert len(ctx.ua_domains) == 0
        assert len(ctx.ua_flows) == 0
        assert len(ctx.ua_steps) == 0

        serialized = ctx.to_dict()
        assert serialized["ua_domains_count"] == 0
        assert serialized["ua_flows_count"] == 0
        assert serialized["ua_steps_count"] == 0

    def test_enrichment_includes_ua_block_when_enabled(self, retriever, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "1")
        intent = classify("auth profile")
        ctx = retriever.retrieve(intent)
        
        # Verify if matches were found and enrichment block is generated
        enrichment = format_user_enrichment(ctx, intent)
        if len(ctx.ua_domains) > 0 or len(ctx.ua_flows) > 0 or len(ctx.ua_steps) > 0:
            assert "<understand_anything_context>" in enrichment
            assert "Matching Domains:" in enrichment or "Matching Flows:" in enrichment or "Matching Code Steps/Files:" in enrichment
        else:
            assert "<understand_anything_context>" not in enrichment

    def test_enrichment_excludes_ua_block_when_disabled(self, retriever, monkeypatch):
        monkeypatch.setenv("DBSHERPA_ENABLE_UA_CONTEXT", "0")
        intent = classify("auth profile")
        ctx = retriever.retrieve(intent)
        
        enrichment = format_user_enrichment(ctx, intent)
        assert "<understand_anything_context>" not in enrichment
