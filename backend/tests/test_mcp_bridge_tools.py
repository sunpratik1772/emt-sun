from __future__ import annotations

from mcp_bridge import tools


def test_should_run_live_allows_atlassian_tools_with_atlassian_integration():
    params = {
        "_credentials": {
            "integration": "atlassian",
            "atlassian": {
                "site_url": "https://example.atlassian.net",
                "email": "user@example.com",
                "api_token": "token123",
            },
        }
    }
    assert tools._should_run_live("confluence_publish_report", params) is True


def test_should_run_live_blocks_cross_vendor_when_integration_explicit_github():
    params = {
        "_credentials": {
            "integration": "github",
            "atlassian": {
                "site_url": "https://example.atlassian.net",
                "email": "user@example.com",
                "api_token": "token123",
            },
        }
    }
    assert tools._should_run_live("confluence_publish_report", params) is False
