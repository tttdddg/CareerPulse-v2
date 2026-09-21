BEGIN;

LOCK TABLE public.student_profile IN ACCESS EXCLUSIVE MODE;

ALTER TABLE public.student_profile
    DROP CONSTRAINT ck_micro_student_profile_basic_info,
    DROP CONSTRAINT ck_micro_student_profile_abilities;

ALTER TABLE public.student_profile
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
        );

COMMIT;
