-- CareerPulse A02 additive schema migration.
-- Existing CareerPulse tables and fields are intentionally untouched.

CREATE TABLE IF NOT EXISTS ability_tags (
    id          SERIAL PRIMARY KEY,
    tag         VARCHAR(64)  NOT NULL UNIQUE,
    category    VARCHAR(32)  NOT NULL CHECK (category IN ('hard_skill', 'product_business', 'soft_skill', 'domain_knowledge', 'certification')),
    difficulty  REAL         NOT NULL DEFAULT 1.0 CHECK (difficulty BETWEEN 1.0 AND 3.0),
    description TEXT,
    deprecated  BOOLEAN      NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_ability_records (
    id          BIGSERIAL PRIMARY KEY,
    student_id  BIGINT       NOT NULL REFERENCES student_profile(id),
    tag         VARCHAR(64)  NOT NULL,
    level       SMALLINT     NOT NULL CHECK (level BETWEEN 1 AND 5),
    confidence  REAL         NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    evidence    TEXT,
    recorded_at TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_student_ability_student ON student_ability_records(student_id);

CREATE TABLE IF NOT EXISTS career_graph_nodes (
    id           SERIAL PRIMARY KEY,
    node_key     VARCHAR(128) NOT NULL UNIQUE,
    job_title    VARCHAR(128) NOT NULL,
    level_range  VARCHAR(16),
    industry     VARCHAR(64),
    description  TEXT
);

CREATE TABLE IF NOT EXISTS career_graph_edges (
    id              SERIAL PRIMARY KEY,
    source_key      VARCHAR(128) NOT NULL REFERENCES career_graph_nodes(node_key),
    target_key      VARCHAR(128) NOT NULL REFERENCES career_graph_nodes(node_key),
    relation_type   VARCHAR(16)  NOT NULL CHECK (relation_type IN ('vertical', 'lateral')),
    reason          TEXT,
    transfer_cost   REAL         NOT NULL DEFAULT 1.0,
    growth_value    REAL         NOT NULL DEFAULT 1.0,
    source_industry VARCHAR(64),
    target_industry VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS idx_graph_source ON career_graph_edges(source_key);
CREATE INDEX IF NOT EXISTS idx_graph_target ON career_graph_edges(target_key);

CREATE TABLE IF NOT EXISTS training_records (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL,
    user_id         VARCHAR(64),
    student_id      BIGINT,
    job_id          INTEGER,
    training_type   VARCHAR(32)  NOT NULL CHECK (training_type IN ('remote_collaboration', 'ai_office_task', 'cross_role_communication')),
    training_data   JSONB        NOT NULL,
    user_answer     TEXT,
    score_data      JSONB,
    created_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    scored_at       TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_training_session ON training_records(session_id);

CREATE TABLE IF NOT EXISTS learning_plans (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(64),
    session_id      VARCHAR(64)  NOT NULL,
    plan_data       JSONB        NOT NULL,
    status          VARCHAR(16)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    created_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS growth_archives (
    id                    BIGSERIAL PRIMARY KEY,
    user_id               VARCHAR(64)  NOT NULL,
    abilities             JSONB        NOT NULL,
    competitiveness_score REAL         NOT NULL,
    completed_trainings   INTEGER      NOT NULL DEFAULT 0,
    completed_phases      INTEGER      NOT NULL DEFAULT 0,
    growth_trend          VARCHAR(16)  NOT NULL DEFAULT 'stable' CHECK (growth_trend IN ('improving', 'stable', 'declining')),
    snapshot_time         TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_growth_user ON growth_archives(user_id);

CREATE TABLE IF NOT EXISTS agent_logs (
    id            BIGSERIAL PRIMARY KEY,
    session_id    VARCHAR(64)  NOT NULL,
    agent_name    VARCHAR(32)  NOT NULL,
    status        VARCHAR(16)  NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
    summary       TEXT,
    duration_ms   INTEGER,
    tool_calls    JSONB,
    fallback_used BOOLEAN      NOT NULL DEFAULT false,
    error         TEXT,
    demo          BOOLEAN      NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_logs_session ON agent_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_agent ON agent_logs(agent_name);

CREATE TABLE IF NOT EXISTS user_feedback (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(64)  NOT NULL,
    user_id         VARCHAR(64)  NOT NULL,
    satisfaction    SMALLINT     NOT NULL CHECK (satisfaction BETWEEN 1 AND 5),
    path_rating     SMALLINT     CHECK (path_rating BETWEEN 1 AND 5),
    training_rating SMALLINT     CHECK (training_rating BETWEEN 1 AND 5),
    resource_rating SMALLINT     CHECK (resource_rating BETWEEN 1 AND 5),
    comments        TEXT,
    created_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

-- ROLLBACK (manual, destructive; execute only after explicit approval):
-- DROP TABLE user_feedback, agent_logs, growth_archives, learning_plans,
--   training_records, career_graph_edges, career_graph_nodes,
--   student_ability_records, ability_tags;
