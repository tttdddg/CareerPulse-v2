BEGIN;

DO $$
BEGIN
    IF to_regclass('identity.app_user') IS NULL THEN
        RAISE EXCEPTION 'V008 identity.app_user migration is required';
    END IF;
    IF to_regclass('public.student_profile') IS NULL THEN
        RAISE EXCEPTION 'public.student_profile is required';
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS identity.user_student_profile (
    user_id       varchar(64) PRIMARY KEY
                  REFERENCES identity.app_user(id) ON DELETE CASCADE,
    student_id    bigint NOT NULL UNIQUE
                  REFERENCES public.student_profile(student_id) ON DELETE RESTRICT,
    linked_at     timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE identity.user_student_profile IS
    'One-to-one ownership link between a verified Web account and a student profile';
COMMENT ON COLUMN identity.user_student_profile.user_id IS
    'Verified identity.app_user id; never accepted from a browser payload';

COMMIT;

-- Manual rollback after verifying no dependent authorization path uses it:
-- DROP TABLE identity.user_student_profile;
