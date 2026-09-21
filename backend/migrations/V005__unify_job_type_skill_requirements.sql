BEGIN;

LOCK TABLE public.job_type_profile IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'job_type_profile'
          AND column_name = 'core_skills'
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'job_type_profile'
          AND column_name = 'optional_skills'
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'job_type_profile'
          AND column_name = 'soft_skills'
    ) THEN
        RAISE EXCEPTION 'job_type_profile legacy skill columns are missing';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'job_type_profile'
          AND column_name = 'skill_requirements'
    ) THEN
        RAISE EXCEPTION 'job_type_profile.skill_requirements already exists';
    END IF;
END
$$;

ALTER TABLE public.job_type_profile
    ADD COLUMN skill_requirements jsonb;

WITH grouped AS (
    SELECT
        profile.type_key,
        profile.level_range,
        skill_group.importance,
        skill_group.group_rank,
        skill_group.group_total,
        skill.tag,
        skill.ordinality
    FROM public.job_type_profile AS profile
    CROSS JOIN LATERAL (
        VALUES
            ('critical', 1, 0.60::numeric, profile.core_skills),
            ('important', 2, 0.25::numeric, profile.optional_skills),
            ('nice_to_have', 3, 0.15::numeric, profile.soft_skills)
    ) AS skill_group(importance, group_rank, group_total, skills)
    CROSS JOIN LATERAL jsonb_array_elements_text(skill_group.skills)
        WITH ORDINALITY AS skill(tag, ordinality)
),
deduplicated AS (
    SELECT
        grouped.*,
        row_number() OVER (
            PARTITION BY type_key, tag
            ORDER BY group_rank, ordinality
        ) AS precedence
    FROM grouped
),
retained AS (
    SELECT *
    FROM deduplicated
    WHERE precedence = 1
),
measured AS (
    SELECT
        retained.*,
        count(*) OVER (
            PARTITION BY type_key, importance
        ) AS group_count,
        row_number() OVER (
            PARTITION BY type_key, importance
            ORDER BY ordinality, tag
        ) AS group_position
    FROM retained
),
weighted AS (
    SELECT
        measured.*,
        CASE
            WHEN group_position = group_count THEN
                group_total
                - round(group_total / group_count, 6) * (group_count - 1)
            ELSE round(group_total / group_count, 6)
        END AS weight,
        CASE level_range
            WHEN 'entry' THEN
                CASE importance
                    WHEN 'critical' THEN 2
                    WHEN 'important' THEN 1
                    ELSE 2
                END
            WHEN 'junior' THEN
                CASE importance
                    WHEN 'critical' THEN 3
                    WHEN 'important' THEN 2
                    ELSE 2
                END
            WHEN 'mid' THEN
                CASE importance
                    WHEN 'critical' THEN 4
                    WHEN 'important' THEN 3
                    ELSE 3
                END
            WHEN 'senior' THEN
                CASE importance
                    WHEN 'critical' THEN 5
                    WHEN 'important' THEN 4
                    ELSE 4
                END
            WHEN 'lead' THEN
                CASE importance
                    WHEN 'critical' THEN 5
                    WHEN 'important' THEN 4
                    ELSE 4
                END
        END AS required_level
    FROM measured
),
assembled AS (
    SELECT
        type_key,
        jsonb_agg(
            jsonb_build_object(
                'tag', tag,
                'required_level', required_level,
                'weight', weight,
                'importance', importance
            )
            ORDER BY group_rank, ordinality, tag
        ) AS skill_requirements
    FROM weighted
    GROUP BY type_key
)
UPDATE public.job_type_profile AS profile
SET skill_requirements = assembled.skill_requirements,
    updated_at = CURRENT_TIMESTAMP
FROM assembled
WHERE profile.type_key = assembled.type_key;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.job_type_profile
        WHERE skill_requirements IS NULL
           OR jsonb_typeof(skill_requirements) <> 'array'
           OR jsonb_array_length(skill_requirements) = 0
    ) THEN
        RAISE EXCEPTION 'skill_requirements must be a non-empty JSON array';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.job_type_profile AS profile
        CROSS JOIN LATERAL jsonb_array_elements(profile.skill_requirements)
            AS skill(item)
        WHERE jsonb_typeof(skill.item) <> 'object'
           OR NOT skill.item ?& ARRAY[
                'tag', 'required_level', 'weight', 'importance'
              ]
           OR jsonb_typeof(skill.item -> 'tag') <> 'string'
           OR jsonb_typeof(skill.item -> 'required_level') <> 'number'
           OR jsonb_typeof(skill.item -> 'weight') <> 'number'
           OR jsonb_typeof(skill.item -> 'importance') <> 'string'
    ) THEN
        RAISE EXCEPTION 'skill_requirements contains an invalid item shape';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.job_type_profile AS profile
        CROSS JOIN LATERAL jsonb_array_elements(profile.skill_requirements)
            AS skill(item)
        WHERE btrim(skill.item ->> 'tag') = ''
           OR (skill.item ->> 'required_level')::numeric < 1
           OR (skill.item ->> 'required_level')::numeric > 5
           OR mod((skill.item ->> 'required_level')::numeric, 1) <> 0
           OR (skill.item ->> 'weight')::numeric <= 0
           OR (skill.item ->> 'weight')::numeric > 1
           OR skill.item ->> 'importance' NOT IN (
                'critical', 'important', 'nice_to_have'
              )
    ) THEN
        RAISE EXCEPTION 'skill_requirements contains an invalid item value';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.job_type_profile AS profile
        WHERE (
            SELECT count(*)
            FROM jsonb_array_elements(profile.skill_requirements)
        ) <> (
            SELECT count(DISTINCT skill.item ->> 'tag')
            FROM jsonb_array_elements(profile.skill_requirements) AS skill(item)
        )
    ) THEN
        RAISE EXCEPTION 'skill_requirements contains duplicate tags';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.job_type_profile AS profile
        WHERE abs((
            SELECT sum((skill.item ->> 'weight')::numeric)
            FROM jsonb_array_elements(profile.skill_requirements) AS skill(item)
        ) - 1.0) > 0.000001
    ) THEN
        RAISE EXCEPTION 'skill_requirements weights must sum to 1';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.job_type_profile AS profile
        WHERE EXISTS (
            SELECT old_skill.tag
            FROM jsonb_array_elements_text(
                profile.core_skills
                || profile.optional_skills
                || profile.soft_skills
            ) AS old_skill(tag)
            EXCEPT
            SELECT new_skill.item ->> 'tag'
            FROM jsonb_array_elements(profile.skill_requirements)
                AS new_skill(item)
        ) OR EXISTS (
            SELECT new_skill.item ->> 'tag'
            FROM jsonb_array_elements(profile.skill_requirements)
                AS new_skill(item)
            EXCEPT
            SELECT old_skill.tag
            FROM jsonb_array_elements_text(
                profile.core_skills
                || profile.optional_skills
                || profile.soft_skills
            ) AS old_skill(tag)
        )
    ) THEN
        RAISE EXCEPTION 'skill_requirements did not preserve the legacy skill set';
    END IF;
END
$$;

ALTER TABLE public.job_type_profile
    ALTER COLUMN skill_requirements SET DEFAULT '[]'::jsonb,
    ALTER COLUMN skill_requirements SET NOT NULL;

ALTER TABLE public.job_type_profile
    ADD CONSTRAINT ck_micro_job_type_skill_requirements
    CHECK (
        jsonb_typeof(skill_requirements) = 'array'
        AND jsonb_array_length(skill_requirements) > 0
        AND NOT jsonb_path_exists(
            skill_requirements,
            '$[*] ? (!exists(@.tag) || !exists(@.required_level) || !exists(@.weight) || !exists(@.importance))'
        )
        AND NOT jsonb_path_exists(
            skill_requirements,
            '$[*] ? (@.tag.type() != "string" || @.tag == "" || @.required_level.type() != "number" || @.required_level < 1 || @.required_level > 5 || @.weight.type() != "number" || @.weight <= 0 || @.weight > 1 || @.importance.type() != "string" || !(@.importance == "critical" || @.importance == "important" || @.importance == "nice_to_have"))'
        )
    );

CREATE INDEX idx_micro_job_type_skill_requirements
    ON public.job_type_profile
    USING gin (skill_requirements jsonb_path_ops);

COMMENT ON COLUMN public.job_type_profile.skill_requirements IS
    'Unified job ability requirements: tag, required_level, weight, importance';

ALTER TABLE public.job_type_profile
    DROP COLUMN core_skills,
    DROP COLUMN optional_skills,
    DROP COLUMN soft_skills;

COMMIT;
