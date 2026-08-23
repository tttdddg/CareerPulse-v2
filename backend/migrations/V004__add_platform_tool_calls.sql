-- CareerPulse A02 minimal Ant TBox stage-3 tool invocation ledger.
-- Stores hashes and a safe CareerState result-field pointer; raw profiles,
-- evidence text, full results, and tokens are omitted.

CREATE TABLE IF NOT EXISTS platform_tool_calls (
    tool_call_id        VARCHAR(64) PRIMARY KEY,
    tool_name           VARCHAR(64) NOT NULL,
    idempotency_key     VARCHAR(128) NOT NULL,
    request_fingerprint CHAR(64) NOT NULL,
    session_id          VARCHAR(128) NOT NULL,
    platform_session_id VARCHAR(128),
    user_id_hash        CHAR(64),
    status              VARCHAR(16) NOT NULL,
    result_data         JSONB,
    error_code          INTEGER,
    error_type          VARCHAR(128),
    agent_run_key       VARCHAR(256),
    duration_ms         INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_platform_tool_call_status CHECK (
        status IN ('running', 'succeeded', 'failed', 'timed_out')
    ),
    CONSTRAINT uq_platform_tool_idempotency UNIQUE (tool_name, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_platform_tool_calls_session
    ON platform_tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_platform_tool_calls_status
    ON platform_tool_calls(status);

-- ROLLBACK (manual, destructive; execute only after explicit approval):
-- DROP TABLE platform_tool_calls;
