#!/usr/bin/env python3
"""Generate the SQLite surveillance demo fixture."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND_ROOT / "demo_data" / "surveillance_fixture.sqlite"


SCHEMA = """
DROP TABLE IF EXISTS leads;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS hs_alerts;
DROP TABLE IF EXISTS hs_orders;
DROP TABLE IF EXISTS hs_exec;
DROP TABLE IF EXISTS hs_trades;
DROP TABLE IF EXISTS market_ticks;
DROP TABLE IF EXISTS comms_messages;

CREATE TABLE leads (
  lead_id TEXT PRIMARY KEY,
  company TEXT NOT NULL,
  region TEXT NOT NULL,
  score REAL NOT NULL,
  stage TEXT NOT NULL
);

CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  sku TEXT NOT NULL,
  region TEXT NOT NULL,
  quantity REAL NOT NULL,
  revenue REAL NOT NULL
);

CREATE TABLE products (
  sku TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit_price REAL NOT NULL
);

CREATE TABLE hs_alerts (
  alert_id TEXT PRIMARY KEY,
  participant_id TEXT NOT NULL,
  trader_id TEXT NOT NULL,
  trader_name TEXT NOT NULL,
  keyword TEXT NOT NULL,
  alert_date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  currency_pair TEXT NOT NULL,
  scenario TEXT NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE hs_orders (
  order_id TEXT PRIMARY KEY,
  alert_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  trader_id TEXT NOT NULL,
  trader_name TEXT NOT NULL,
  book TEXT NOT NULL,
  currency_pair TEXT NOT NULL,
  order_time TEXT NOT NULL,
  side TEXT NOT NULL,
  quantity REAL NOT NULL,
  limit_price REAL NOT NULL,
  order_type TEXT NOT NULL,
  status TEXT NOT NULL,
  venue TEXT NOT NULL
);

CREATE TABLE hs_exec (
  exec_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  alert_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  trader_id TEXT NOT NULL,
  trader_name TEXT NOT NULL,
  book TEXT NOT NULL,
  currency_pair TEXT NOT NULL,
  exec_time TEXT NOT NULL,
  side TEXT NOT NULL,
  exec_quantity REAL NOT NULL,
  exec_price REAL NOT NULL,
  venue TEXT NOT NULL,
  counterparty TEXT NOT NULL,
  notional_usd REAL NOT NULL,
  trade_version INTEGER NOT NULL,
  lifecycle_event TEXT NOT NULL
);

CREATE TABLE hs_trades (
  trade_id TEXT PRIMARY KEY,
  exec_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  alert_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  trader_id TEXT NOT NULL,
  trader_name TEXT NOT NULL,
  book TEXT NOT NULL,
  currency_pair TEXT NOT NULL,
  trade_time TEXT NOT NULL,
  side TEXT NOT NULL,
  trade_quantity REAL NOT NULL,
  trade_price REAL NOT NULL,
  counterparty TEXT NOT NULL,
  notional_usd REAL NOT NULL,
  risk_flag TEXT NOT NULL
);

CREATE TABLE market_ticks (
  tick_id TEXT PRIMARY KEY,
  alert_id TEXT NOT NULL,
  currency_pair TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  symbol TEXT NOT NULL,
  bid REAL NOT NULL,
  ask REAL NOT NULL,
  mid REAL NOT NULL,
  spread_pips REAL NOT NULL,
  bid_size REAL NOT NULL,
  ask_size REAL NOT NULL,
  venue_name TEXT NOT NULL,
  query_type TEXT NOT NULL DEFAULT 'fxperiodtick',
  seq_no INTEGER NOT NULL
);

CREATE TABLE comms_messages (
  message_id TEXT PRIMARY KEY,
  alert_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  trader_id TEXT NOT NULL,
  trader_name TEXT NOT NULL,
  book TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  keyword TEXT NOT NULL,
  channel TEXT NOT NULL,
  display_post TEXT NOT NULL,
  event_type TEXT NOT NULL,
  relevance_score REAL NOT NULL
);
"""


TRADERS = [
    ("P-T001", "T001", "Avery Shah"),
    ("P-T002", "T002", "Morgan Lee"),
    ("P-T003", "T003", "Riley Chen"),
    ("P-T004", "T004", "Sam Patel"),
    ("P-T005", "T005", "Jordan Blake"),
    ("P-T006", "T006", "Nina Okafor"),
    ("P-T007", "T007", "Leo Martin"),
    ("P-T008", "T008", "Maya Iyer"),
    ("P-T009", "T009", "Chris Novak"),
    ("P-T010", "T010", "Elena Rossi"),
]

PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF", "EUR/GBP", "NZD/USD", "USD/CAD"]
BOOKS = ["FX-SPOT", "FX-FWD", "FX-SWAPS", "FX-OPTIONS", "MACRO-HEDGE", "JPY-HEDGE", "COMMODITY-HEDGE"]
KEYWORDS = ["fixing", "client flow", "large order", "pre hedge", "risk transfer", "stop loss"]
COUNTERPARTIES = ["JPM", "CITI", "BARC", "GS", "MS", "UBS"]
VENUES = ["Bloomberg", "EBS", "Reuters", "360T"]

RICH_ALERT_BOOKS = {
    1: ["FX-SPOT", "FX-FWD", "FX-OPTIONS"],
    2: ["FX-SPOT", "FX-SWAPS", "FX-FWD", "MACRO-HEDGE"],
    3: ["FX-SPOT", "JPY-HEDGE"],
    4: ["FX-SPOT", "FX-FWD", "COMMODITY-HEDGE"],
    5: ["FX-SPOT", "FX-FWD", "FX-SWAPS", "FX-OPTIONS", "MACRO-HEDGE"],
}


def _iso(base: str, minutes: int) -> str:
    return (datetime.fromisoformat(base) + timedelta(minutes=minutes)).isoformat()


def _alert(idx: int) -> dict:
    participant_id, trader_id, trader_name = TRADERS[(idx - 1) % len(TRADERS)]
    day = ((idx - 1) % 31) + 1
    hour = 8 + ((idx * 3) % 8)
    minute = (idx * 7) % 45
    start = datetime(2024, 1, day, hour, minute)
    positive = idx <= 3 or (idx > 5 and idx % 4 in {1, 2})
    pair = PAIRS[(idx - 1) % len(PAIRS)]
    keyword = KEYWORDS[(idx - 1) % len(KEYWORDS)]
    return {
        "alert_id": f"ALERT-FR-{idx:03d}",
        "participant_id": participant_id,
        "trader_id": trader_id,
        "trader_name": trader_name,
        "keyword": keyword,
        "alert_date": start.date().isoformat(),
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(minutes=45)).isoformat(),
        "currency_pair": pair,
        "scenario": "front_running_positive" if positive else "front_running_negative",
        "description": (
            f"{pair} {keyword} surveillance window for {trader_name}; "
            f"{'pre-client trading and communications align' if positive else 'activity is explainable by normal hedging/liquidity'}."
        ),
        "positive": positive,
        "books": RICH_ALERT_BOOKS.get(idx, [BOOKS[(idx - 1) % len(BOOKS)]]),
    }


def _insert_alert(conn: sqlite3.Connection, alert: dict) -> None:
    conn.execute(
        """
        INSERT INTO hs_alerts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert["alert_id"],
            alert["participant_id"],
            alert["trader_id"],
            alert["trader_name"],
            alert["keyword"],
            alert["alert_date"],
            alert["start_time"],
            alert["end_time"],
            alert["currency_pair"],
            alert["scenario"],
            alert["description"],
        ),
    )


def _insert_lifecycle(conn: sqlite3.Connection, alert: dict, row_no: int, book: str, sequence: int) -> None:
    side = "BUY" if (row_no + sequence) % 2 else "SELL"
    quantity = 750_000 + (row_no % 37) * 25_000 + sequence * 50_000
    base_price = 1.04 + (row_no % 19) * 0.004 + sequence * 0.0007
    order_id = f"ORD-{row_no:05d}"
    exec_id = f"EXE-{row_no:05d}"
    trade_id = f"TRD-{row_no:05d}"
    order_time = _iso(alert["start_time"], 2 + sequence * 3)
    exec_time = _iso(alert["start_time"], 4 + sequence * 3)
    trade_time = _iso(alert["start_time"], 5 + sequence * 3)
    venue = VENUES[row_no % len(VENUES)]
    counterparty = COUNTERPARTIES[row_no % len(COUNTERPARTIES)]
    risk_flag = (
        "PRE_CLIENT_ACTIVITY"
        if alert["positive"] and sequence == 0
        else "RELATED_BOOK_ACTIVITY"
        if alert["positive"]
        else "NORMAL_MARKET_MAKING"
    )
    conn.execute(
        """
        INSERT INTO hs_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            alert["alert_id"],
            alert["participant_id"],
            alert["trader_id"],
            alert["trader_name"],
            book,
            alert["currency_pair"],
            order_time,
            side,
            quantity,
            round(base_price, 5),
            "LIMIT" if row_no % 3 else "MARKET",
            "FILLED",
            venue,
        ),
    )
    conn.execute(
        """
        INSERT INTO hs_exec VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            exec_id,
            order_id,
            alert["alert_id"],
            alert["participant_id"],
            alert["trader_id"],
            alert["trader_name"],
            book,
            alert["currency_pair"],
            exec_time,
            side,
            quantity * 0.92,
            round(base_price + 0.0003, 5),
            venue,
            counterparty,
            round(quantity * (base_price + 0.0003), 2),
            1,
            "EXECUTED_AFTER_ORDER",
        ),
    )
    conn.execute(
        """
        INSERT INTO hs_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            exec_id,
            order_id,
            alert["alert_id"],
            alert["participant_id"],
            alert["trader_id"],
            alert["trader_name"],
            book,
            alert["currency_pair"],
            trade_time,
            side,
            quantity * 0.92,
            round(base_price + 0.0005, 5),
            counterparty,
            round(quantity * (base_price + 0.0005), 2),
            risk_flag,
        ),
    )


def _insert_market(conn: sqlite3.Connection, alert: dict, row_no: int, sequence: int) -> None:
    bid = 1.03 + (row_no % 23) * 0.003 + sequence * 0.00009
    ask = bid + 0.00016 + (sequence % 4) * 0.00002
    conn.execute(
        """
        INSERT INTO market_ticks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"TICK-{row_no:05d}",
            alert["alert_id"],
            alert["currency_pair"],
            _iso(alert["start_time"], sequence * 2),
            alert["currency_pair"],
            round(bid, 5),
            round(ask, 5),
            round((bid + ask) / 2, 5),
            round((ask - bid) * 10000, 2),
            1_500_000 + sequence * 35_000,
            1_700_000 + sequence * 31_000,
            "EBS" if sequence % 2 else "Reuters",
            "fxperiodtick" if sequence % 2 == 0 else "forwardperiodtick",
            row_no,
        ),
    )


def _insert_comms(conn: sqlite3.Connection, alert: dict, row_no: int, book: str, sequence: int) -> None:
    positive_text = (
        f"{alert['trader_name']} said '{alert['keyword']}' and discussed selling before the client order in {book}."
    )
    negative_text = (
        f"{alert['trader_name']} discussed routine {alert['currency_pair']} liquidity checks in {book}."
    )
    conn.execute(
        """
        INSERT INTO comms_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"MSG-{row_no:05d}",
            alert["alert_id"],
            alert["participant_id"],
            alert["trader_id"],
            alert["trader_name"],
            book,
            _iso(alert["start_time"], 1 + sequence * 3),
            alert["keyword"],
            "CHAT" if sequence % 2 else "VOICE_TRANSCRIPT",
            positive_text if alert["positive"] else negative_text,
            "BLOOMBERG_MSG" if sequence % 2 else "VOICE",
            0.94 - (sequence % 5) * 0.04 if alert["positive"] else 0.35,
        ),
    )


def generate() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        alerts = [_alert(idx) for idx in range(1, 501)]
        for alert in alerts:
            _insert_alert(conn, alert)

        lifecycle_row = 1
        for idx, alert in enumerate(alerts, start=1):
            books = alert["books"] if idx <= 5 else [alert["books"][0]]
            for seq, book in enumerate(books):
                if lifecycle_row > 500:
                    break
                _insert_lifecycle(conn, alert, lifecycle_row, book, seq)
                lifecycle_row += 1
            if lifecycle_row > 500:
                break

        market_row = 1
        for idx, alert in enumerate(alerts, start=1):
            tick_count = 20 if idx <= 5 else 1
            for seq in range(tick_count):
                if market_row > 500:
                    break
                _insert_market(conn, alert, market_row, seq)
                market_row += 1
            if market_row > 500:
                break

        comms_row = 1
        for idx, alert in enumerate(alerts, start=1):
            msg_count = 10 if idx <= 5 else 1
            for seq in range(msg_count):
                if comms_row > 500:
                    break
                book = alert["books"][seq % len(alert["books"])]
                _insert_comms(conn, alert, comms_row, book, seq)
                comms_row += 1
            if comms_row > 500:
                break

        _seed_demo_catalog_tables(conn)
        conn.commit()

    print(f"Generated {DB_PATH}")


def _seed_demo_catalog_tables(conn: sqlite3.Connection) -> None:
    """Studio demo tables (formerly inline CSV metadata)."""
    leads = [
        ("L001", "Acme Corp", "EU", 92, "negotiation"),
        ("L002", "Beta Labs", "US", 68, "discovery"),
        ("L003", "Coral AI", "APAC", 88, "proposal"),
        ("L004", "Delta Fin", "US", 54, "nurture"),
        ("L005", "Echo Health", "EU", 79, "discovery"),
        ("L006", "Flux Media", "MEA", 95, "negotiation"),
    ]
    conn.executemany(
        "INSERT INTO leads VALUES (?, ?, ?, ?, ?)",
        leads,
    )
    orders = [
        ("O-101", "SKU-100", "EU", 3, 897),
        ("O-102", "SKU-200", "US", 5, 745),
        ("O-103", "SKU-100", "APAC", 2, 598),
        ("O-104", "SKU-300", "US", 1, 199),
        ("O-105", "SKU-200", "EU", 4, 596),
    ]
    conn.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
        orders,
    )
    products = [
        ("SKU-100", "Workflow Pro", "platform", 299),
        ("SKU-200", "MCP Bridge", "integration", 149),
        ("SKU-300", "Agent Pack", "ai", 199),
    ]
    conn.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?)",
        products,
    )


if __name__ == "__main__":
    generate()
