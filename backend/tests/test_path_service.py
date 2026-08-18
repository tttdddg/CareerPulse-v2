import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from app.schemas.job_schema import JobProfile
from app.schemas.match_schema import MatchResult
from app.schemas.path_schema import PathResult, UserPreferences
from app.schemas.profile_schema import StudentProfile
from app.services.career_graph_repository import CareerGraphRepository
from app.services.match_service import MatchService
from app.services.path_service import PathService
from app.services.path_config import MAX_CONSECUTIVE_LATERAL, MAX_PATH_NODES


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"


def load_json(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


class DisconnectedEntryRepository(CareerGraphRepository):
    """Keep valid seed structure but expose no outgoing transitions from entries."""

    def outgoing_edges(self, node_key):
        node = self.node(node_key)
        if node is not None and node.level_range == "entry":
            return ()
        return super().outgoing_edges(node_key)


class SearchOnlyRepository:
    def __init__(self, node_count, relation_type):
        self.nodes = tuple(range(node_count))
        self._edges = {
            f"n{index}": (
                SimpleNamespace(
                    source_key=f"n{index}",
                    target_key=f"n{index + 1}",
                    relation_type=relation_type,
                ),
            )
            for index in range(node_count - 1)
        }

    def outgoing_edges(self, node_key):
        return self._edges.get(node_key, ())


class CareerGraphRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.graph_data = load_json("career_graph.json")
        self.repository = CareerGraphRepository(graph=self.graph_data)

    def test_seed_graph_structure_and_queries(self):
        self.assertEqual(len(self.repository.nodes), 10)
        self.assertEqual(len(self.repository.edges), 16)
        self.assertEqual(
            [item.node_key for item in self.repository.entry_roles()],
            ["ai-product-assistant", "backend-trainee", "data-assistant", "data-product-assistant"],
        )
        self.assertEqual(
            [item.node_key for item in self.repository.next_roles("data-assistant")],
            ["data-analyst"],
        )
        self.assertEqual(
            [item.node_key for item in self.repository.parallel_roles("data-assistant")],
            ["data-product-assistant"],
        )
        node, flags = self.repository.resolved_node("data-analyst")
        self.assertEqual(sum(item.weight for item in node.required_skills), 1.0)
        self.assertEqual(flags, [])

    def test_cycle_detection_reports_real_lateral_cycles(self):
        cycles = self.repository.detect_cycles()
        self.assertTrue(cycles)
        self.assertTrue(all(cycle[0] == cycle[-1] for cycle in cycles))
        self.assertIn(
            ["ai-product-assistant", "data-analyst", "ai-product-assistant"],
            cycles,
        )

    def test_missing_node_skills_fall_back_to_same_title_job_profile(self):
        graph = copy.deepcopy(self.graph_data)
        node = next(item for item in graph["nodes"] if item["node_key"] == "data-analyst")
        node["required_skills"] = None
        jobs = load_json("jobs_demo.json")
        repository = CareerGraphRepository(graph=graph, job_profiles=jobs)

        resolved, flags = repository.resolved_node("data-analyst")

        self.assertIsNotNone(resolved.required_skills)
        self.assertIn("node_skill_vector_fallback:data-analyst", flags)
        self.assertEqual(resolved.required_skills[0].tag, "数据分析")

    def test_missing_node_skills_without_job_profile_is_explicit_error(self):
        graph = copy.deepcopy(self.graph_data)
        graph["nodes"][0]["required_skills"] = None
        repository = CareerGraphRepository(graph=graph)
        with self.assertRaisesRegex(ValueError, "no required_skills"):
            repository.resolved_node(graph["nodes"][0]["node_key"])

    def test_invalid_vertical_edge_and_isolated_node_are_rejected(self):
        inverted = copy.deepcopy(self.graph_data)
        edge = next(item for item in inverted["edges"] if item["relation_type"] == "vertical")
        edge["source_key"], edge["target_key"] = edge["target_key"], edge["source_key"]
        with self.assertRaisesRegex(ValueError, "strictly increase"):
            CareerGraphRepository(graph=inverted)

        isolated = copy.deepcopy(self.graph_data)
        isolated_key = isolated["nodes"][0]["node_key"]
        isolated["edges"] = [
            edge
            for edge in isolated["edges"]
            if edge["source_key"] != isolated_key and edge["target_key"] != isolated_key
        ]
        template = copy.deepcopy(isolated["edges"][0])
        for source, target in (
            ("backend-trainee", "data-product-assistant"),
            ("backend-trainee", "ai-product-assistant"),
        ):
            extra = copy.deepcopy(template)
            extra.update(
                {
                    "source_key": source,
                    "target_key": target,
                    "relation_type": "lateral",
                    "source_industry": "企业服务/SaaS",
                }
            )
            isolated["edges"].append(extra)
        self.assertGreaterEqual(len(isolated["edges"]), 15)
        with self.assertRaisesRegex(ValueError, "isolated"):
            CareerGraphRepository(graph=isolated)


class PathServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.students = load_json("students_demo.json")
        cls.jobs = load_json("jobs_demo.json")
        cls.match_service = MatchService()

    def build_inputs(self, student_index=2, job_index=1, *, job_override=None):
        student = StudentProfile.model_validate(self.students[student_index])
        raw_job = copy.deepcopy(self.jobs[job_index])
        if job_override:
            raw_job.update(job_override)
        job = JobProfile.model_validate(raw_job)
        match = MatchResult.model_validate(self.match_service.calculate(student, job))
        return student, job, match

    def calculate(self, student_index=2, job_index=1, **kwargs):
        student, job, match = self.build_inputs(student_index, job_index)
        return PathService().calculate(student, job, match, kwargs.get("preferences", {}), kwargs.get("years", 3))

    def test_data_analyst_path_has_score_and_distinct_roadmaps(self):
        result = self.calculate(2, 1)
        validated = PathResult.model_validate(result)

        self.assertEqual(validated.status, "success")
        self.assertEqual(
            [node.node_key for node in validated.recommended_path.nodes],
            ["data-assistant", "data-analyst"],
        )
        self.assertEqual(len(validated.three_year_roadmap.stages), 3)
        self.assertEqual(len(validated.five_year_roadmap.stages), 5)
        self.assertNotEqual(
            validated.three_year_roadmap.model_dump(),
            validated.five_year_roadmap.model_dump(),
        )
        score = validated.recommended_path.score
        self.assertAlmostEqual(
            score.base_score,
            score.growth_value - score.transfer_cost - score.ability_gap_cost,
            places=4,
        )
        self.assertEqual(
            set(validated.path_scores),
            {item.path_id for item in validated.candidate_paths},
        )

    def test_ai_product_graph_produces_direct_and_extension_candidates(self):
        result = PathResult.model_validate(self.calculate(0, 0))
        types = {item.path_type for item in result.candidate_paths}
        self.assertIn("direct", types)
        self.assertIn("extension", types)
        self.assertIn("candidate_type_unavailable:robust", result.data_quality_flags)
        self.assertTrue(
            all(node.node_key for item in result.candidate_paths for node in item.nodes)
        )

    def test_search_is_cycle_safe_and_respects_limits(self):
        service = PathService()
        paths = service._search_paths("data-assistant", "ai-product-manager")
        self.assertTrue(paths)
        for path in paths:
            self.assertEqual(len(path), len(set(path)))
            self.assertLessEqual(len(path), MAX_PATH_NODES)
            lateral_run = 0
            for source, target in zip(path, path[1:]):
                edge = next(
                    item for item in service.repository.outgoing_edges(source)
                    if item.target_key == target
                )
                lateral_run = lateral_run + 1 if edge.relation_type == "lateral" else 0
                self.assertLessEqual(lateral_run, MAX_CONSECUTIVE_LATERAL)

    def test_search_explicitly_prunes_long_and_repeated_lateral_paths(self):
        long_chain = PathService(repository=SearchOnlyRepository(8, "vertical"))
        lateral_chain = PathService(repository=SearchOnlyRepository(4, "lateral"))

        self.assertEqual(long_chain._search_paths("n0", "n7"), [])
        self.assertEqual(lateral_chain._search_paths("n0", "n3"), [])

    def test_unknown_target_uses_graph_node_fallback_without_inferred_node(self):
        student, job, match = self.build_inputs(
            2,
            1,
            job_override={
                "title": "量化业务分析师",
                "normalized_title": "量化业务分析师",
            },
        )
        result = PathResult.model_validate(PathService().calculate(student, job, match, {}, 3))

        self.assertEqual(result.status, "success")
        self.assertTrue(result.recommended_path.fallback_target)
        self.assertNotEqual(result.recommended_path.nodes[-1].job_title, "量化业务分析师")
        self.assertIn("target_not_in_graph:量化业务分析师", result.data_quality_flags)
        self.assertEqual(result.recommended_path.score.target_consistency, 0.5)

    def test_no_reachable_path_returns_explicit_empty_result(self):
        student, job, match = self.build_inputs(2, 1)
        service = PathService(repository=DisconnectedEntryRepository())

        result = PathResult.model_validate(service.calculate(student, job, match, {}, 3))

        self.assertEqual(result.status, "no_reachable_path")
        self.assertEqual(result.candidate_paths, [])
        self.assertIsNone(result.recommended_path)
        self.assertEqual(result.three_year_roadmap.stages, [])
        self.assertIn("no_reachable_path", result.data_quality_flags)

    def test_unresolved_entry_skill_vectors_return_insufficient_data(self):
        graph = load_json("career_graph.json")
        for node in graph["nodes"]:
            if node["level_range"] == "entry":
                node["required_skills"] = None
        repository = CareerGraphRepository(graph=graph)
        student, job, match = self.build_inputs(2, 1)

        result = PathResult.model_validate(
            PathService(repository=repository).calculate(student, job, match, {}, 3)
        )

        self.assertEqual(result.status, "insufficient_data")
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(any(flag.startswith("unresolved_start_data") for flag in result.data_quality_flags))

    def test_one_unresolved_entry_is_skipped_when_other_entries_are_valid(self):
        graph = load_json("career_graph.json")
        node = next(item for item in graph["nodes"] if item["node_key"] == "ai-product-assistant")
        node["required_skills"] = None
        repository = CareerGraphRepository(graph=graph)
        student, job, match = self.build_inputs(2, 1)

        result = PathResult.model_validate(
            PathService(repository=repository).calculate(student, job, match, {}, 3)
        )

        self.assertEqual(result.status, "success")
        self.assertIn("entry_node_unresolved:ai-product-assistant", result.data_quality_flags)

    def test_city_is_not_invented_and_does_not_change_score(self):
        student, job, match = self.build_inputs(2, 1)
        without_city = PathResult.model_validate(PathService().calculate(student, job, match, {}, 3))
        with_city = PathResult.model_validate(
            PathService().calculate(student, job, match, {"desired_city": "上海"}, 3)
        )
        self.assertEqual(
            without_city.recommended_path.score.total_score,
            with_city.recommended_path.score.total_score,
        )
        self.assertIsNone(with_city.recommended_path.score.region_fit)
        self.assertIn("city_data_unavailable", with_city.data_quality_flags)

    def test_unknown_node_skills_reduce_data_confidence_without_fake_gap(self):
        result = PathResult.model_validate(self.calculate(0, 0))
        flagged = [
            item
            for item in result.candidate_paths
            if any(flag.startswith("node_match_has_unknown_skills") for flag in item.data_quality_flags)
        ]
        self.assertTrue(flagged)
        self.assertTrue(all(item.score.data_confidence < 1.0 for item in flagged))

    def test_growth_and_risk_components_are_monotonic(self):
        student, job, match = self.build_inputs(2, 1)
        base_graph = load_json("career_graph.json")
        higher_growth = copy.deepcopy(base_graph)
        riskier = copy.deepcopy(base_graph)
        growth_edge = next(
            item for item in higher_growth["edges"]
            if item["source_key"] == "data-assistant" and item["target_key"] == "data-analyst"
        )
        growth_edge["growth_value"] += 2.0
        risk_node = next(item for item in riskier["nodes"] if item["node_key"] == "data-assistant")
        risk_node["risk_level"] = "high"

        base = PathResult.model_validate(
            PathService(CareerGraphRepository(graph=base_graph)).calculate(student, job, match, {}, 3)
        )
        growth = PathResult.model_validate(
            PathService(CareerGraphRepository(graph=higher_growth)).calculate(student, job, match, {}, 3)
        )
        risk = PathResult.model_validate(
            PathService(CareerGraphRepository(graph=riskier)).calculate(student, job, match, {}, 3)
        )
        self.assertGreater(growth.recommended_path.score.total_score, base.recommended_path.score.total_score)
        self.assertLess(risk.recommended_path.score.total_score, base.recommended_path.score.total_score)

    def test_target_stage_reuses_input_match_gaps(self):
        student, job, match = self.build_inputs(2, 1)
        result = PathResult.model_validate(PathService().calculate(student, job, match, {}, 3))
        target_stages = [
            stage
            for stage in result.five_year_roadmap.stages
            if stage.target_role == job.normalized_title
        ]
        self.assertTrue(target_stages)
        self.assertEqual(
            target_stages[-1].current_gaps,
            match.skill_gaps[:3],
        )

    def test_same_input_is_exactly_deterministic(self):
        student, job, match = self.build_inputs(0, 0)
        service = PathService()
        first = service.calculate(
            student,
            job,
            match,
            UserPreferences(preferred_path_type="extension"),
            5,
        )
        for _ in range(10):
            self.assertEqual(
                service.calculate(
                    student,
                    job,
                    match,
                    UserPreferences(preferred_path_type="extension"),
                    5,
                ),
                first,
            )

    def test_invalid_horizon_and_malformed_match_result_are_rejected(self):
        student, job, match = self.build_inputs(2, 1)
        with self.assertRaises(ValidationError):
            PathService().calculate(student, job, match, {}, 4)
        bad_match = match.model_dump()
        bad_match["confidence"] = 1.5
        with self.assertRaises(ValidationError):
            PathService().calculate(student, job, bad_match, {}, 3)

    def test_match_result_for_different_target_returns_insufficient_data(self):
        student = StudentProfile.model_validate(self.students[2])
        data_job = JobProfile.model_validate(self.jobs[1])
        backend_job = JobProfile.model_validate(self.jobs[2])
        wrong_match = MatchResult.model_validate(
            self.match_service.calculate(student, backend_job)
        )

        result = PathResult.model_validate(
            PathService().calculate(student, data_job, wrong_match, {}, 3)
        )

        self.assertEqual(result.status, "insufficient_data")
        self.assertIn("match_result_target_mismatch", result.data_quality_flags)


if __name__ == "__main__":
    unittest.main()
