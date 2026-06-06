-- dbSherpa Studio — SQLite schema (local dev default)
-- Version: 5 (matches database_scope.SCHEMA_VERSION)
--
-- File created at runtime: backend/copilot_chats.db
-- Apply: python backend/scripts/apply_sqlite_schema.py
--        or python backend/scripts/reset_db.py (drop + init_db)

PRAGMA foreign_keys = ON;

-- Auth
CREATE TABLE IF NOT EXISTS users (
    user_id       VARCHAR(255) PRIMARY KEY,
    username      VARCHAR(255) UNIQUE,
    email         VARCHAR(255) UNIQUE,
    name          VARCHAR(255),
    picture       VARCHAR(255),
    password_hash VARCHAR(255),
    auth_provider VARCHAR(50),
    role          VARCHAR(32) NOT NULL DEFAULT 'user',
    created_at    TEXT,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS user_sessions (
    session_token VARCHAR(255) PRIMARY KEY,
    user_id       VARCHAR(255),
    expires_at    TEXT,
    created_at    TEXT
);

-- Workflows (per user)
CREATE TABLE IF NOT EXISTS workflows (
    user_id         VARCHAR(255) NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    workflow_id     VARCHAR(255),
    name            VARCHAR(255),
    description     TEXT,
    workflow_data   TEXT,
    upvote_count    INTEGER DEFAULT 0,
    downvote_count  INTEGER DEFAULT 0,
    updated_at      TEXT,
    PRIMARY KEY (user_id, filename)
);

CREATE TABLE IF NOT EXISTS drafts (
    user_id       VARCHAR(255) NOT NULL,
    filename      VARCHAR(255) NOT NULL,
    workflow_id   VARCHAR(255),
    name          VARCHAR(255),
    description   TEXT,
    workflow_data TEXT,
    updated_at    TEXT,
    PRIMARY KEY (user_id, filename)
);

CREATE TABLE IF NOT EXISTS workflow_votes (
    voter_user_id VARCHAR(255) NOT NULL,
    owner_user_id VARCHAR(255) NOT NULL,
    filename      VARCHAR(255) NOT NULL,
    vote          VARCHAR(10) NOT NULL,
    created_at    TEXT,
    PRIMARY KEY (voter_user_id, owner_user_id, filename)
);

CREATE TABLE IF NOT EXISTS good_examples (
    id                 VARCHAR(255) PRIMARY KEY,
    source_user_id     VARCHAR(255) NOT NULL,
    source_filename    VARCHAR(255) NOT NULL,
    workflow_id        VARCHAR(255),
    name               VARCHAR(255),
    description        TEXT,
    workflow_data      TEXT NOT NULL,
    promoted_at        TEXT,
    promote_to_folder  INTEGER DEFAULT 1,
    promote_to_table   INTEGER DEFAULT 1,
    folder_path        TEXT
);

-- Copilot
CREATE TABLE IF NOT EXISTS copilot_chats (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id    VARCHAR(255),
    title      VARCHAR(255),
    updated_at TEXT,
    messages   TEXT
);

CREATE TABLE IF NOT EXISTS user_memory (
    user_id    VARCHAR(255) PRIMARY KEY,
    content    TEXT NOT NULL,
    updated_at TEXT
);

-- Access control
CREATE TABLE IF NOT EXISTS user_skills (
    user_id    VARCHAR(255) NOT NULL,
    skill_id   VARCHAR(255) NOT NULL,
    is_owner   INTEGER DEFAULT 0,
    created_at TEXT,
    PRIMARY KEY (user_id, skill_id)
);

CREATE TABLE IF NOT EXISTS user_data_source_access (
    user_id    VARCHAR(255) NOT NULL,
    source_id  VARCHAR(255) NOT NULL,
    has_access INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, source_id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id    VARCHAR(255) NOT NULL,
    pref_key   VARCHAR(255) NOT NULL,
    pref_value TEXT NOT NULL,
    updated_at TEXT,
    PRIMARY KEY (user_id, pref_key)
);

CREATE TABLE IF NOT EXISTS user_feature_access (
    user_id     VARCHAR(255) NOT NULL,
    feature_key VARCHAR(64) NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, feature_key)
);

-- Runs
CREATE TABLE IF NOT EXISTS run_logs (
    run_id       VARCHAR(255) PRIMARY KEY,
    user_id      VARCHAR(255),
    workflow     VARCHAR(255),
    started_at   TEXT,
    finished_at  TEXT,
    duration_ms  INTEGER,
    status       VARCHAR(50),
    disposition  VARCHAR(255),
    node_count   INTEGER,
    edge_count   INTEGER,
    flag_count   INTEGER,
    error        TEXT,
    report_path  TEXT,
    download_url TEXT,
    run_log      TEXT,
    run_result   TEXT,
    run_error    TEXT
);

CREATE TABLE IF NOT EXISTS run_artifacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          VARCHAR(255) NOT NULL,
    source_node_id  VARCHAR(255),
    file_name       VARCHAR(500),
    artifact_type   VARCHAR(50),
    file_path       TEXT,
    download_url    TEXT,
    generated_at    TEXT,
    UNIQUE(run_id, source_node_id, file_name, download_url)
);

-- Automations
CREATE TABLE IF NOT EXISTS automations (
    id                      VARCHAR(255) PRIMARY KEY,
    user_id                 VARCHAR(255),
    name                    VARCHAR(255),
    workflow_filename       VARCHAR(255),
    schedule_type           VARCHAR(50),
    cron_expression         VARCHAR(255),
    interval_mins           INTEGER,
    duration_mins           INTEGER,
    active                  INTEGER,
    author                  VARCHAR(255),
    output_filename_pattern TEXT,
    created_at              TEXT,
    updated_at              TEXT
);

CREATE TABLE IF NOT EXISTS automation_runs (
    id            VARCHAR(255) PRIMARY KEY,
    automation_id VARCHAR(255),
    run_id        VARCHAR(255),
    status        VARCHAR(50),
    triggered_at  TEXT,
    duration_ms   INTEGER,
    error         TEXT,
    download_url  TEXT,
    FOREIGN KEY(automation_id) REFERENCES automations(id)
);
