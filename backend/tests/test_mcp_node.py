from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from engine.context import RunContext
from engine.nodes.mcp import run as mcp_run


def test_mcp_node_page_title_override() -> None:
    node = {
        "id": "mcp1",
        "type": "mcp",
        "config": {
            "integration": "confluence",
            "tool": "confluence_publish_report",
            "pageTitle": "My Custom Confluence Title Override",
            "params": {},
        },
    }
    ctx = RunContext()
    incoming = {}

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"success": True}]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        
        asyncio.run(mcp_run(node, ctx, incoming))
        
        assert mock_post.called
        args, kwargs = mock_post.call_args
        body = kwargs.get("json", {})
        params = body.get("params", {})
        assert params.get("title") == "My Custom Confluence Title Override"
