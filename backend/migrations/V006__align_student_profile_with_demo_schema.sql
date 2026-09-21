BEGIN;

LOCK TABLE public.student_profile IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'student_profile'
          AND column_name = 'id'
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'student_profile'
          AND column_name = 'parsed_data'
    ) THEN
        RAISE EXCEPTION 'student_profile legacy columns are missing';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'student_profile'
          AND column_name IN (
              'student_id', 'name', 'basic_info', 'abilities',
              'competitiveness_score', 'completeness', 'missing_fields'
          )
    ) THEN
        RAISE EXCEPTION 'student_profile target columns already exist';
    END IF;
END
$$;

ALTER TABLE public.student_profile
    DROP CONSTRAINT ck_micro_student_profile_structure,
    DROP CONSTRAINT ck_micro_student_profile_city,
    DROP CONSTRAINT ck_micro_student_profile_target_industry,
    DROP CONSTRAINT ck_micro_student_profile_supplementary;

ALTER TABLE public.student_profile
    RENAME COLUMN id TO student_id;

ALTER TABLE public.student_profile
    ADD COLUMN name varchar(64),
    ADD COLUMN basic_info jsonb,
    ADD COLUMN abilities jsonb,
    ADD COLUMN competitiveness_score numeric(5, 2),
    ADD COLUMN completeness numeric(4, 3),
    ADD COLUMN missing_fields jsonb;

WITH migrated_abilities AS (
    SELECT
        profile.student_id,
        jsonb_agg(
            jsonb_build_object(
                'tag', skill.tag,
                'level', 1,
                'confidence', 0.0,
                'evidence', '历史画像仅记录技能标签，能力等级与证据待补充'
            )
            ORDER BY skill.ordinality
        ) AS abilities
    FROM public.student_profile AS profile
    CROSS JOIN LATERAL jsonb_array_elements_text(profile.parsed_data -> 'skills')
        WITH ORDINALITY AS skill(tag, ordinality)
    GROUP BY profile.student_id
)
UPDATE public.student_profile AS profile
SET
    name = '匿名学生-' || profile.student_id,
    basic_info = jsonb_build_object(
        'education_level', profile.parsed_data #>> '{education,degree}',
        'major', profile.parsed_data #>> '{education,major}',
        'graduation_year', profile.parsed_data #> '{education,graduation_year}',
        'target_job', profile.parsed_data -> 'target_job',
        'target_industry', profile.parsed_data -> 'target_industry',
        'years_of_experience', NULL
    ),
    abilities = migrated_abilities.abilities,
    competitiveness_score = 0.0,
    completeness = round((
        0.2 * (
            (
                ((profile.parsed_data #>> '{education,degree}') IS NOT NULL)::integer
                + ((profile.parsed_data #>> '{education,major}') IS NOT NULL)::integer
                + ((profile.parsed_data #>> '{education,graduation_year}') IS NOT NULL)::integer
            ) / 3.0
            + (
                ((profile.parsed_data ->> 'target_job') IS NOT NULL)::integer
                + ((profile.parsed_data ->> 'target_industry') IS NOT NULL)::integer
            ) / 2.0
            + CASE
                WHEN jsonb_array_length(profile.parsed_data -> 'internships') > 0
                THEN 1.0 ELSE 0.0
              END
            + CASE
                WHEN jsonb_array_length(profile.parsed_data -> 'projects') > 0
                THEN 1.0 ELSE 0.0
              END
            + LEAST(
                jsonb_array_length(profile.parsed_data -> 'skills') / 3.0,
                1.0
              )
        )
    )::numeric, 3),
    missing_fields = to_jsonb(
        ARRAY['能力等级与证据']::text[]
        || CASE
            WHEN jsonb_array_length(profile.parsed_data -> 'internships') = 0
            THEN ARRAY['实习经历']::text[]
            ELSE ARRAY[]::text[]
           END
    ),
    updated_at = CURRENT_TIMESTAMP
FROM migrated_abilities
WHERE profile.student_id = migrated_abilities.student_id;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.student_profile
        WHERE name IS NULL
           OR basic_info IS NULL
           OR abilities IS NULL
           OR competitiveness_score IS NULL
           OR completeness IS NULL
           OR missing_fields IS NULL
    ) THEN
        RAISE EXCEPTION 'student_profile migration left null target fields';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.student_profile
        WHERE jsonb_typeof(basic_info) <> 'object'
           OR jsonb_typeof(abilities) <> 'array'
           OR jsonb_array_length(abilities) < 3
           OR jsonb_array_length(abilities) > 30
           OR jsonb_typeof(missing_fields) <> 'array'
           OR competitiveness_score < 0
           OR competitiveness_score > 100
           OR completeness < 0
           OR completeness > 1
    ) THEN
        RAISE EXCEPTION 'student_profile migration produced invalid target values';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.student_profile AS profile
        CROSS JOIN LATERAL jsonb_array_elements(profile.abilities) AS ability(item)
        WHERE jsonb_typeof(ability.item) <> 'object'
           OR NOT ability.item ?& ARRAY['tag', 'level', 'confidence', 'evidence']
           OR jsonb_typeof(ability.item -> 'tag') <> 'string'
           OR jsonb_typeof(ability.item -> 'level') <> 'number'
           OR jsonb_typeof(ability.item -> 'confidence') <> 'number'
           OR jsonb_typeof(ability.item -> 'evidence') <> 'string'
    ) THEN
        RAISE EXCEPTION 'student_profile abilities contain an invalid item shape';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.student_profile AS profile
        WHERE (
            SELECT count(*)
            FROM jsonb_array_elements(profile.abilities)
        ) <> (
            SELECT count(DISTINCT ability.item ->> 'tag')
            FROM jsonb_array_elements(profile.abilities) AS ability(item)
        )
    ) THEN
        RAISE EXCEPTION 'student_profile abilities contain duplicate tags';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.student_profile AS profile
        WHERE EXISTS (
            SELECT old_skill.tag
            FROM jsonb_array_elements_text(profile.parsed_data -> 'skills') AS old_skill(tag)
            EXCEPT
            SELECT new_ability.item ->> 'tag'
            FROM jsonb_array_elements(profile.abilities) AS new_ability(item)
        ) OR EXISTS (
            SELECT new_ability.item ->> 'tag'
            FROM jsonb_array_elements(profile.abilities) AS new_ability(item)
            EXCEPT
            SELECT old_skill.tag
            FROM jsonb_array_elements_text(profile.parsed_data -> 'skills') AS old_skill(tag)
        )
    ) THEN
        RAISE EXCEPTION 'student_profile migration did not preserve skill tags';
    END IF;
END
$$;

ALTER TABLE public.student_profile
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN basic_info SET NOT NULL,
    ALTER COLUMN abilities SET NOT NULL,
    ALTER COLUMN competitiveness_score SET NOT NULL,
    ALTER COLUMN completeness SET NOT NULL,
    ALTER COLUMN missing_fields SET DEFAULT '[]'::jsonb,
    ALTER COLUMN missing_fields SET NOT NULL;

ALTER TABLE public.student_profile
    ADD CONSTRAINT ck_micro_student_profile_name
        CHECK (char_length(btrim(name)) BETWEEN 1 AND 64),
    ADD CONSTRAINT ck_micro_student_profile_basic_info
        CHECK (
            jsonb_typeof(basic_info) = 'object'
            AND basic_info ?& ARRAY[
                'education_level', 'major', 'graduation_year',
                'target_job', 'target_industry', 'years_of_experience'
            ]
            AND NOT jsonb_path_exists(
                basic_info,
                '$ ? (@.education_level.type() != "string" || !(@.education_level == "专科" || @.education_level == "本科" || @.education_level == "硕士" || @.education_level == "博士") || @.major.type() != "string" || @.major == "" || @.target_job.type() != "string" || @.target_job == "" || !(@.target_industry.type() == "string" || @.target_industry.type() == "null") || !(@.graduation_year.type() == "number" || @.graduation_year.type() == "null") || (@.graduation_year.type() == "number" && (@.graduation_year.floor() != @.graduation_year || @.graduation_year < 1900 || @.graduation_year > 2200)) || !(@.years_of_experience.type() == "number" || @.years_of_experience.type() == "null") || (@.years_of_experience.type() == "number" && @.years_of_experience < 0))'
            )
        ),
    ADD CONSTRAINT ck_micro_student_profile_abilities
        CHECK (
            jsonb_typeof(abilities) = 'array'
            AND jsonb_array_length(abilities) BETWEEN 3 AND 30
            AND NOT jsonb_path_exists(
                abilities,
                '$[*] ? (!exists(@.tag) || !exists(@.level) || !exists(@.confidence) || !exists(@.evidence))'
            )
            AND NOT jsonb_path_exists(
                abilities,
                '$[*] ? (@.tag.type() != "string" || @.tag == "" || @.level.type() != "number" || @.level.floor() != @.level || @.level < 1 || @.level > 5 || @.confidence.type() != "number" || @.confidence < 0 || @.confidence > 1 || @.evidence.type() != "string" || @.evidence == "")'
            )
        ),
    ADD CONSTRAINT ck_micro_student_profile_competitiveness
        CHECK (competitiveness_score BETWEEN 0 AND 100),
    ADD CONSTRAINT ck_micro_student_profile_completeness
        CHECK (completeness BETWEEN 0 AND 1),
    ADD CONSTRAINT ck_micro_student_profile_missing_fields
        CHECK (
            jsonb_typeof(missing_fields) = 'array'
            AND NOT jsonb_path_exists(
                missing_fields,
                '$[*] ? (@.type() != "string" || @ == "")'
            )
        );

CREATE INDEX idx_micro_student_profile_abilities
    ON public.student_profile
    USING gin (abilities jsonb_path_ops);

CREATE INDEX idx_micro_student_profile_target_job
    ON public.student_profile ((basic_info ->> 'target_job'));

COMMENT ON COLUMN public.student_profile.name IS
    'Display name; use anonymized or masked values outside trusted storage';
COMMENT ON COLUMN public.student_profile.basic_info IS
    'StudentDemo basic_info object';
COMMENT ON COLUMN public.student_profile.abilities IS
    'Evidence-backed ability list: tag, level, confidence, evidence';
COMMENT ON COLUMN public.student_profile.competitiveness_score IS
    'Deterministically calculated cache, not user or LLM input';
COMMENT ON COLUMN public.student_profile.completeness IS
    'Profile completeness in the range 0 to 1';
COMMENT ON COLUMN public.student_profile.missing_fields IS
    'Missing information prompts represented as a JSON string array';

ALTER TABLE public.student_profile
    DROP COLUMN parsed_data;

COMMIT;
