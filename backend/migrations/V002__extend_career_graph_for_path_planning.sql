-- CareerPulse A02 stage 3 career graph extensions.
-- Additive and idempotent; V001 remains unchanged.

ALTER TABLE career_graph_nodes
    ADD COLUMN IF NOT EXISTS required_skills JSONB,
    ADD COLUMN IF NOT EXISTS typical_duration INTEGER,
    ADD COLUMN IF NOT EXISTS risk_level VARCHAR(16),
    ADD COLUMN IF NOT EXISTS cities JSONB;

ALTER TABLE career_graph_nodes
    DROP CONSTRAINT IF EXISTS ck_graph_node_typical_duration;
ALTER TABLE career_graph_nodes
    ADD CONSTRAINT ck_graph_node_typical_duration
    CHECK (typical_duration IS NULL OR typical_duration BETWEEN 1 AND 120);

ALTER TABLE career_graph_nodes
    DROP CONSTRAINT IF EXISTS ck_graph_node_risk_level;
ALTER TABLE career_graph_nodes
    ADD CONSTRAINT ck_graph_node_risk_level
    CHECK (risk_level IS NULL OR risk_level IN ('low', 'medium', 'high'));

ALTER TABLE career_graph_edges
    ADD COLUMN IF NOT EXISTS transition_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS risk_level VARCHAR(16) NOT NULL DEFAULT 'medium';

CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_edge_identity
    ON career_graph_edges(source_key, target_key, relation_type);

ALTER TABLE career_graph_edges
    DROP CONSTRAINT IF EXISTS ck_graph_edge_risk_level;
ALTER TABLE career_graph_edges
    ADD CONSTRAINT ck_graph_edge_risk_level
    CHECK (risk_level IN ('low', 'medium', 'high'));

-- ROLLBACK (manual, destructive; execute only after explicit approval):
-- ALTER TABLE career_graph_edges DROP COLUMN transition_requirements, DROP COLUMN risk_level;
-- ALTER TABLE career_graph_nodes DROP COLUMN required_skills, DROP COLUMN typical_duration,
--   DROP COLUMN risk_level, DROP COLUMN cities;
