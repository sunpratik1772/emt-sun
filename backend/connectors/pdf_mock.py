"""Demo PDF fixtures for the pdf_extract node — not part of the data catalog."""
from __future__ import annotations

PDF_MOCK: dict[str, dict] = {
    "default": {
        "pages": 4,
        "text": (
            "Executive Summary\n\nThis document outlines the Q1 2026 performance metrics. "
            "Total revenue reached $2.4M, up 34% YoY."
        ),
    },
    "contract.pdf": {
        "pages": 8,
        "text": "SERVICE AGREEMENT\n\nProvider agrees to deliver workflow automation services.",
    },
    "report.pdf": {
        "pages": 12,
        "text": "MARKET RESEARCH REPORT 2026\n\nThe automation market is projected to grow rapidly.",
    },
}
