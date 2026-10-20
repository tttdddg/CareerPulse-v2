BEGIN;

CREATE SCHEMA IF NOT EXISTS identity;

CREATE TABLE IF NOT EXISTS identity.app_user (
    id                  varchar(64)  PRIMARY KEY,
    username            varchar(32)  NOT NULL,
    username_normalized varchar(32)  NOT NULL UNIQUE,
    email               varchar(254) NOT NULL,
    email_normalized    varchar(254) NOT NULL UNIQUE,
    password_hash       text         NOT NULL,
    role                varchar(32)  NOT NULL DEFAULT 'user',
    status              varchar(16)  NOT NULL DEFAULT 'active',
    created_at          timestamptz  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          timestamptz  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_identity_user_status CHECK (status IN ('active', 'disabled')),
    CONSTRAINT ck_identity_username_not_blank CHECK (btrim(username) <> ''),
    CONSTRAINT ck_identity_email_not_blank CHECK (btrim(email) <> '')
);

CREATE TABLE IF NOT EXISTS identity.auth_session (
    session_token_hash char(64)    PRIMARY KEY,
    user_id            varchar(64) NOT NULL REFERENCES identity.app_user(id) ON DELETE CASCADE,
    created_at         timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at         timestamptz NOT NULL,
    last_seen_at       timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at         timestamptz,
    CONSTRAINT ck_identity_session_hash CHECK (session_token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_identity_session_expiry CHECK (expires_at > created_at)
);
CREATE INDEX IF NOT EXISTS idx_identity_session_user
    ON identity.auth_session(user_id);
CREATE INDEX IF NOT EXISTS idx_identity_session_expiry
    ON identity.auth_session(expires_at) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS identity.auth_login_attempt (
    id           bigserial PRIMARY KEY,
    rate_key     char(64)    NOT NULL,
    attempted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_identity_rate_key CHECK (rate_key ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS idx_identity_login_attempt_window
    ON identity.auth_login_attempt(rate_key, attempted_at DESC);

COMMIT;

-- Manual rollback after verifying no dependent production data:
-- DROP SCHEMA identity CASCADE;

