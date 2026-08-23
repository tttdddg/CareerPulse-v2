-- CareerPulse A02 stage 3 durable CareerState and idempotent AgentRunLog.
-- Additive migration; existing business tables and public fields are preserved.

CREATE TABLE IF NOT EXISTS career_state (
    session_id          VARCHAR(128) PRIMARY KEY,
    platform_session_id VARCHAR(128),
    user_id             VARCHAR(128),
    status              VARCHAR(32) NOT NULL DEFAULT 'INITIALIZED',
    error_type          VARCHAR(128),
    state_data          JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_career_state_status CHECK (status IN (
        'INITIALIZED',
        'PROFILE_STARTED', 'PROFILE_COMPLETED',
        'JOB_STARTED', 'JOB_COMPLETED',
        'MATCH_STARTED', 'MATCH_COMPLETED',
        'PATH_STARTED', 'PATH_COMPLETED',
        'TRAINING_STARTED', 'TRAINING_COMPLETED',
        'FEEDBACK_STARTED', 'FEEDBACK_COMPLETED',
        'COMPLETED', 'PARTIAL', 'FAILED'
    ))
);
CREATE INDEX IF NOT EXISTS idx_career_state_user ON career_state(user_id);

ALTER TABLE agent_logs
    ALTER COLUMN session_id TYPE VARCHAR(128),
    ALTER COLUMN agent_name TYPE VARCHAR(64),
    ADD COLUMN IF NOT EXISTS service_name VARCHAR(64),
    ADD COLUMN IF NOT EXISTS run_key VARCHAR(256);

-- Legacy rows retain null run_key. New stage-3 writes always provide one and
-- can therefore be safely retried without adding duplicate Agent logs.
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_logs_run_key
    ON agent_logs(run_key)
    WHERE run_key IS NOT NULL;

-- ROLLBACK (manual, destructive; execute only after explicit approval):
-- DROP INDEX uq_agent_logs_run_key;
-- ALTER TABLE agent_logs DROP COLUMN run_key, DROP COLUMN service_name;
-- DROP TABLE career_state;

