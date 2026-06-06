-- dbSherpa Studio — MySQL 8 / Google Cloud SQL schema
-- Version: 5 (matches database_scope.SCHEMA_VERSION)
--
-- Apply:
--   mysql -h HOST -u USER -p DATABASE < backend/sql/001_schema_mysql.sql
--   python backend/scripts/apply_mysql_schema.py
--   python backend/scripts/verify_schema.py
--
-- After schema: start the API once (init_db seeds John Doe + optional workflow files)
-- or run: python backend/scripts/reset_db.py  (destructive — dev only)

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------------
-- Auth & identity
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    user_id       VARCHAR(255)  NOT NULL PRIMARY KEY,
    username      VARCHAR(255)  NULL UNIQUE,
    email         VARCHAR(255)  NULL UNIQUE,
    name          VARCHAR(255)  NULL,
    picture       VARCHAR(255)  NULL,
    password_hash VARCHAR(255)  NULL,
    auth_provider VARCHAR(50)   NULL,
    role          VARCHAR(32)   NOT NULL DEFAULT 'user',
    created_at    DATETIME      NULL,
    last_login_at DATETIME      NULL,
    INDEX idx_users_username (username),
    INDEX idx_users_email (email),
    INDEX idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_sessions (
    session_token VARCHAR(255) NOT NULL PRIMARY KEY,
    user_id       VARCHAR(255) NULL,
    expires_at    DATETIME     NULL,
    created_at    DATETIME     NULL,
    INDEX idx_user_sessions_user_id (user_id),
    INDEX idx_user_sessions_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Per-user workspace (workflows owned by user_id)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workflows (
    user_id         VARCHAR(255) NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    workflow_id     VARCHAR(255) NULL,
    name            VARCHAR(255) NULL,
    description     TEXT         NULL,
    workflow_data   LONGTEXT     NULL,
    upvote_count    INT          NOT NULL DEFAULT 0,
    downvote_count  INT          NOT NULL DEFAULT 0,
    updated_at      DATETIME     NULL,
    PRIMARY KEY (user_id, filename),
    INDEX idx_workflows_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS drafts (
    user_id       VARCHAR(255) NOT NULL,
    filename      VARCHAR(255) NOT NULL,
    workflow_id   VARCHAR(255) NULL,
    name          VARCHAR(255) NULL,
    description   TEXT         NULL,
    workflow_data LONGTEXT     NULL,
    updated_at    DATETIME     NULL,
    PRIMARY KEY (user_id, filename),
    INDEX idx_drafts_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workflow_votes (
    voter_user_id VARCHAR(255) NOT NULL,
    owner_user_id VARCHAR(255) NOT NULL,
    filename      VARCHAR(255) NOT NULL,
    vote          VARCHAR(10)  NOT NULL,
    created_at    DATETIME     NULL,
    PRIMARY KEY (voter_user_id, owner_user_id, filename),
    INDEX idx_workflow_votes_owner (owner_user_id, filename)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS good_examples (
    id                 VARCHAR(255)  NOT NULL PRIMARY KEY,
    source_user_id     VARCHAR(255)  NOT NULL,
    source_filename    VARCHAR(255)  NOT NULL,
    workflow_id        VARCHAR(255)  NULL,
    name               VARCHAR(255)  NULL,
    description        TEXT          NULL,
    workflow_data      LONGTEXT      NOT NULL,
    promoted_at        DATETIME      NULL,
    promote_to_folder  TINYINT       NOT NULL DEFAULT 1,
    promote_to_table   TINYINT       NOT NULL DEFAULT 1,
    folder_path        VARCHAR(1000) NULL,
    INDEX idx_good_examples_source (source_user_id, source_filename)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Copilot & per-user memory
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS copilot_chats (
    session_id VARCHAR(255) NOT NULL PRIMARY KEY,
    user_id    VARCHAR(255) NULL,
    title      VARCHAR(255) NULL,
    updated_at DATETIME     NULL,
    messages   LONGTEXT     NULL,
    INDEX idx_copilot_chats_user (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_memory (
    user_id    VARCHAR(255) NOT NULL PRIMARY KEY,
    content    LONGTEXT     NOT NULL,
    updated_at DATETIME     NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Access control (admin-managed grants)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS user_skills (
    user_id    VARCHAR(255) NOT NULL,
    skill_id   VARCHAR(255) NOT NULL,
    is_owner   TINYINT      NOT NULL DEFAULT 0,
    created_at DATETIME     NULL,
    PRIMARY KEY (user_id, skill_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_data_source_access (
    user_id    VARCHAR(255) NOT NULL,
    source_id  VARCHAR(255) NOT NULL,
    has_access TINYINT      NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id    VARCHAR(255) NOT NULL,
    pref_key   VARCHAR(255) NOT NULL,
    pref_value TEXT         NOT NULL,
    updated_at DATETIME     NULL,
    PRIMARY KEY (user_id, pref_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_feature_access (
    user_id     VARCHAR(255) NOT NULL,
    feature_key VARCHAR(64)  NOT NULL,
    enabled     TINYINT      NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, feature_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Run history
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS run_logs (
    run_id       VARCHAR(255) NOT NULL PRIMARY KEY,
    user_id      VARCHAR(255) NULL,
    workflow     VARCHAR(255) NULL,
    started_at   VARCHAR(64)  NULL,
    finished_at  VARCHAR(64)  NULL,
    duration_ms  INT          NULL,
    status       VARCHAR(50)  NULL,
    disposition  VARCHAR(255) NULL,
    node_count   INT          NULL,
    edge_count   INT          NULL,
    flag_count   INT          NULL,
    error        TEXT         NULL,
    report_path  VARCHAR(500) NULL,
    download_url VARCHAR(500) NULL,
    run_log      LONGTEXT     NULL,
    run_result   LONGTEXT     NULL,
    run_error    TEXT         NULL,
    INDEX idx_run_logs_user_started (user_id, started_at),
    INDEX idx_run_logs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS run_artifacts (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id          VARCHAR(255)  NOT NULL,
    source_node_id  VARCHAR(255)  NULL,
    file_name       VARCHAR(500)  NULL,
    artifact_type   VARCHAR(50)   NULL,
    file_path       VARCHAR(1000) NULL,
    download_url    VARCHAR(1000) NULL,
    generated_at    VARCHAR(64)   NULL,
    UNIQUE KEY uniq_run_artifact (run_id, source_node_id, file_name, download_url(255)),
    INDEX idx_run_artifacts_run_id (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Automations
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS automations (
    id                      VARCHAR(255)  NOT NULL PRIMARY KEY,
    user_id                 VARCHAR(255)  NULL,
    name                    VARCHAR(255)  NULL,
    workflow_filename       VARCHAR(255)  NULL,
    schedule_type           VARCHAR(50)   NULL,
    cron_expression         VARCHAR(255)  NULL,
    interval_mins           INT           NULL,
    duration_mins           INT           NULL,
    active                  TINYINT       NULL,
    author                  VARCHAR(255)  NULL,
    output_filename_pattern VARCHAR(500)  NULL,
    created_at              DATETIME      NULL,
    updated_at              DATETIME      NULL,
    INDEX idx_automations_user (user_id),
    INDEX idx_automations_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS automation_runs (
    id             VARCHAR(255) NOT NULL PRIMARY KEY,
    automation_id  VARCHAR(255) NULL,
    run_id         VARCHAR(255) NULL,
    status         VARCHAR(50)  NULL,
    triggered_at   DATETIME     NULL,
    duration_ms    INT          NULL,
    error          TEXT         NULL,
    download_url   VARCHAR(500) NULL,
    INDEX idx_automation_runs_automation (automation_id),
    INDEX idx_automation_runs_run (run_id),
    CONSTRAINT fk_automation_runs_automation
        FOREIGN KEY (automation_id) REFERENCES automations(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
