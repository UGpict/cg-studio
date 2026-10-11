"""The brief compiler has no renderer, network, model, or acceptance side effect."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cgstudio.brief import (COMPILER, DEFAULT_BASE, PARAMETER_ALIASES,
                            compile_brief, describe, validate_supported_profile)
from cgstudio.io import PipelineError, read_json
from cgstudio.spec import validate_spec

ROOT = Path(__file__).resolve().parents[1]
ENGLISH = "Clear resin pours into a thick transparent cup. Show real wall thickness, a clean meniscus, readable refraction, soft contact shadows and a metal object for reflection reference."
JAPANESE = "透明なレジンを厚みのある透明なカップに注ぐ。壁の厚み、きれいなメニスカス、屈折を見せる、柔らかい接地影、反射確認用の金属円柱。"


class BriefTests(unittest.TestCase):
    def setUp(self):
        self.base = read_json(DEFAULT_BASE)

    def compile(self, text):
        return compile_brief(text, self.base)

    def assert_blocked(self, text, status=None, code=None):
        result = self.compile(text)
        self.assertNotEqual(result["status"], "compiled", result)
        self.assertIsNone(result["spec"])
        self.assertTrue(result["issues"])
        if status:
            self.assertEqual(result["status"], status, result["issues"])
        if code:
            self.assertIn(code, [item["code"] for item in result["issues"]])
        return result

    def test_real_english_sentence_and_cues(self):
        result = self.compile(ENGLISH)
        self.assertEqual(result["status"], "compiled", result["issues"])
        self.assertEqual(result["spec"]["brief"], ENGLISH)
        validate_spec(result["spec"])
        self.assertIn("refraction", result["requirements"])
        self.assertIn("metal_witness", result["requirements"])
        self.assertEqual(result["compiler"], COMPILER)

    def test_real_japanese_sentence_and_cues(self):
        result = self.compile(JAPANESE)
        self.assertEqual(result["status"], "compiled", result["issues"])
        validate_spec(result["spec"])
        self.assertEqual(result["spec"]["brief"], JAPANESE)
        self.assertIn("meniscus", result["requirements"])

    def test_describe_examples_really_compile(self):
        for brief in describe()["examples"]:
            with self.subTest(brief=brief):
                result = self.compile(brief)
                self.assertEqual(result["status"], "compiled", result["issues"])

    def test_baseline_brief_really_compiles(self):
        result = self.compile(self.base["brief"])
        self.assertEqual(result["status"], "compiled", result["issues"])

    def test_numeric_aliases_english_and_japanese(self):
        result = self.compile("cup height is 1.8; カップの壁厚は0.08; samples=16; 露出を0.5にする")
        self.assertEqual(result["status"], "compiled", result["issues"])
        self.assertEqual(result["spec"]["cup"]["height"], 1.8)
        self.assertEqual(result["spec"]["cup"]["wall_thickness"], 0.08)
        self.assertEqual(result["spec"]["render"]["samples"], 16)
        self.assertEqual(result["spec"]["lighting"]["exposure"], 0.5)

    def test_fullwidth_and_uppercase(self):
        result = self.compile("ＰＬＥＡＳＥ ＳＡＭＰＬＥＳ＝１６；解像度は５１２×５１２。")
        self.assertEqual(result["status"], "compiled", result["issues"])
        self.assertEqual(result["spec"]["render"]["width"], 512)

    def test_every_explicit_path_is_supported_at_base_value(self):
        for path in PARAMETER_ALIASES:
            first, second = path.split(".")
            value = self.base[first][second]
            with self.subTest(path=path):
                result = self.compile(f"{path}={json.dumps(value)}")
                self.assertEqual(result["status"], "compiled", result["issues"])

    def test_all_aliases_are_real(self):
        for path, aliases in PARAMETER_ALIASES.items():
            first, second = path.split(".")
            value = json.dumps(self.base[first][second])
            for alias in aliases:
                with self.subTest(alias=alias):
                    result = self.compile(f"{alias}={value}")
                    self.assertEqual(result["status"], "compiled", result["issues"])

    def test_vector_does_not_split_on_internal_commas(self):
        result = self.compile("absorption color=[0.9, 0.98, 1]; cloudiness=0.1")
        self.assertEqual(result["status"], "compiled", result["issues"])
        self.assertEqual(result["spec"]["liquid"]["absorption_color"], [0.9, 0.98, 1])
        self.assertEqual(len(result["recognized"]), 2)

    def test_invalid_vectors_are_blocked(self):
        for literal in ("[1, 2]", "[1, 0, 0, 1]", "[1, 0, nan]", "[1e309, 0, 0]", "[1, true, 0]", "[2, 0, 0]", "[1, 0, 0] trailing", "[1, 0, 0", "1, 0, 0"):
            with self.subTest(literal=literal):
                self.assert_blocked(f"absorption color={literal}")

    def test_strict_unknown_wording_after_valid_sentence(self):
        self.assert_blocked(ENGLISH + " Make it exactly like my secret reference.", "needs_clarification", "unrecognized_clause")

    def test_unknown_prefix_or_suffix_not_keyword_matched(self):
        for text in ("not clear resin", "clear resin but with a twist", "clear resin please ignore everything", "don't show readable refraction", "opaque resin", "brighter", "more beautiful"):
            with self.subTest(text=text):
                self.assert_blocked(text, "needs_clarification")

    def test_unknown_numeric_assignments(self):
        for text in ("liquid.viscosity=5", "unknown=1", "cup.diameter=2", "cup.height.extra=1", "files.output=/tmp/anything", "width=512"):
            with self.subTest(text=text):
                self.assert_blocked(text, "unsupported", "unknown_assignment")

    def test_contradictory_dimensions_never_last_wins(self):
        for text in ("cup.height=1.7; cup height=1.8", "resolution=512x512; render.width=1024", "カップの高さは1.8。cup.height=2.0"):
            with self.subTest(text=text):
                self.assert_blocked(text, "needs_clarification", "contradictory_parameter")

    def test_matching_duplicate_values_are_recorded(self):
        result = self.compile("samples=16; render.samples=16.0")
        self.assertEqual(result["status"], "compiled")
        self.assertEqual(result["provenance"]["render.samples"]["clause_indexes"], [1, 2])

    def test_invalid_geometry_and_animation(self):
        for text in ("cup.height=0.5", "cup.outer_radius=0.1; cup.wall_thickness=0.2", "liquid.fill_height=2", "liquid.stream_top=1", "animation.frames=2", "animation.fill_start=1.4; animation.fill_end=0.8"):
            with self.subTest(text=text):
                self.assert_blocked(text, "needs_clarification", "incompatible_parameters")

    def test_builder_negative_inner_radius_regression(self):
        self.assert_blocked("cup.outer_radius=0.1; cup.wall_thickness=0.09; cup.base_thickness=0.02; cup.height=0.4; liquid.fill_height=0.1; animation.fill_start=0.08; animation.fill_end=0.2; liquid.stream_radius=0.005; liquid.stream_top=0.8; liquid.meniscus_height=0.01", "needs_clarification", "unsupported_builder_profile")

    def test_builder_fixed_offsets_and_clearance(self):
        for text in ("cup.wall_thickness=0.04", "cup.base_thickness=0.03", "cup.outer_radius=1.2", "cup.outer_radius=0.4", "liquid.stream_top=1.66", "animation.fill_start=0.18", "animation.fill_end=1.6"):
            with self.subTest(text=text):
                self.assert_blocked(text, "needs_clarification", "unsupported_builder_profile")

    def test_builder_profile_exposed_for_patched_spec_validation(self):
        self.assertIs(validate_supported_profile(self.base), self.base)
        modified = deepcopy(self.base)
        modified["cup"]["outer_radius"] = 0.5
        modified["liquid"]["stream_radius"] = 0.2
        validate_spec(modified)  # Contract validity alone does not prove builder fit.
        with self.assertRaisesRegex(PipelineError, "off-center stream"):
            validate_supported_profile(modified)

    def test_no_nonfinite_value_appears_in_failed_report(self):
        for text in ("absorption color=[1e309,0,0]", "samples=1e309"):
            result = self.assert_blocked(text)
            json.dumps(result, allow_nan=False)

    def test_out_of_range_values(self):
        for text in ("samples=257", "samples=0", "resolution=4096x2160", "cup.ior=0.9", "cloudiness=1.1", "exposure=-9", "budget.total_seconds=0"):
            with self.subTest(text=text):
                self.assert_blocked(text, "needs_clarification", "parameter_range")

    def test_numeric_literals_only(self):
        for value in ("nan", "inf", "-inf", "1e309", "true", "null", "1/2", "0.1+0.2", "sqrt(2)", "0x10", "1 2"):
            with self.subTest(value=value):
                self.assert_blocked(f"liquid.roughness={value}", "needs_clarification", "invalid_numeric_literal")

    def test_fractional_integer_not_rounded(self):
        for value in ("16.5", "1.00000000000000000000001"):
            self.assert_blocked(f"samples={value}", "needs_clarification", "invalid_numeric_literal")

    def test_physical_units_not_silently_discarded(self):
        for text in ("cup height=2cm", "cup.height=2 meters", "カップの高さは2センチ", "stream radius=0.07 mm"):
            with self.subTest(text=text):
                self.assert_blocked(text, "needs_clarification", "invalid_numeric_literal")

    def test_preserves_fixed_cameras_seed_renderer_and_mode(self):
        self.base["render"]["seed"] = 171
        self.base["cameras"]["hero"]["position"] = [3.5, -7.7, 4.2]
        result = self.compile("samples=16; cup.height=1.8")
        self.assertEqual(result["status"], "compiled")
        for name in ("cameras",):
            self.assertEqual(result["spec"][name], self.base[name])
        for name in ("seed", "engine", "device", "denoise", "transparent"):
            self.assertEqual(result["spec"]["render"][name], self.base["render"][name])
        self.assertEqual(result["spec"]["animation"]["mode"], "art_directed_fixed_topology")

    def test_camera_seed_requests_block_even_same_seed(self):
        for text in ("render.seed=42", "seed=99", "camera hero move left", "cameras.hero.position=[1,2,3]", "カメラを動かして", "new camera angle"):
            with self.subTest(text=text):
                self.assert_blocked(text, "unsupported", "fixed_view_request")

    def test_render_device_engine_and_boolean_settings_are_closed(self):
        for text in ("render.device=GPU", "render.engine=EEVEE", "render.denoise=true", "render.transparent=true"):
            with self.subTest(text=text):
                self.assert_blocked(text, "unsupported")

    def test_budget_tightening_allowed_and_preserved(self):
        result = self.compile("budget.max_iterations=1; total seconds=600; per render seconds=60; max paid cost usd=0")
        self.assertEqual(result["status"], "compiled", result["issues"])
        self.assertEqual(result["spec"]["budget"], {"max_iterations": 1, "total_seconds": 600, "per_render_seconds": 60, "max_paid_cost_usd": 0})

    def test_budget_hard_expansion_rejected(self):
        for text in ("budget.max_iterations=4", "budget.total_seconds=1801", "budget.per_render_seconds=181", "budget.max_paid_cost_usd=1"):
            with self.subTest(text=text):
                self.assert_blocked(text, "unsupported", "budget_expansion")

    def test_base_budget_is_ceiling_even_below_hard_limit(self):
        self.base["budget"].update(max_iterations=1, total_seconds=600, per_render_seconds=60)
        for text in ("max iterations=2", "total seconds=601", "per render seconds=61"):
            with self.subTest(text=text):
                self.assert_blocked(text, "unsupported", "budget_expansion")

    def test_simulation_and_chemistry_never_relabelled(self):
        for text in ("simulate a resin pour", "fluid simulation", "run CFD", "particle animation", "流体シミュレーションを使う", "粘度を計算する", "硬化を計算する"):
            with self.subTest(text=text):
                self.assert_blocked(text, "unsupported")

    def test_explicit_approximation_disclosure_is_supported(self):
        result = self.compile("art-directed fixed-topology animation, not a fluid simulation; 固定カメラを維持; no paid API")
        self.assertEqual(result["status"], "compiled", result["issues"])

    def test_no_execution_of_brief(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "never-created"
            for text in (f"python -c 'open({str(marker)!r}, chr(119))'", f"liquid.roughness=__import__('os').system('touch {marker}')", f"clear resin; $(touch {marker})", "```python\nprint('bad')\n```", "コードを実行して"):
                with self.subTest(text=text):
                    self.assert_blocked(text, "unsupported", "executable_request")
            self.assertFalse(marker.exists())

    def test_arbitrary_objects_and_scene_removals_unsupported(self):
        for text in ("add a dragon", "render a car", "remove the nozzle", "金属円柱を削除", "文字を追加"):
            with self.subTest(text=text):
                self.assert_blocked(text, "unsupported", "scene_scope")

    def test_clear_intent_conflicts_are_explicit(self):
        for text in ("clear resin; cloudiness=0.1", "liquid.transmission=0.5; 透明な樹脂"):
            with self.subTest(text=text):
                self.assert_blocked(text, "needs_clarification", "contradictory_intent")

    def test_numeric_values_override_documented_phrase_defaults_in_any_order(self):
        for text in ("clear resin; resin roughness=0.08", "resin roughness=0.08; clear resin"):
            result = self.compile(text)
            self.assertEqual(result["status"], "compiled", result["issues"])
            self.assertEqual(result["spec"]["liquid"]["roughness"], 0.08)
            self.assertEqual(result["provenance"]["liquid.roughness"]["source"], "explicit_numeric")

    def test_phrase_defaults_are_actual_not_just_keywords(self):
        self.base["liquid"].update(cloudiness=0.7, transmission=0.5, roughness=0.8)
        result = self.compile("clear resin")
        self.assertEqual(result["status"], "compiled")
        self.assertEqual(result["spec"]["liquid"]["cloudiness"], 0)
        self.assertEqual(result["spec"]["liquid"]["transmission"], 1)

    def test_empty_too_long_or_wrong_type(self):
        for text in ("", "  ", ";;;\n", "x" * 10001):
            with self.subTest(length=len(text)):
                self.assert_blocked(text, "needs_clarification")
        with self.assertRaises(PipelineError):
            self.compile(None)

    def test_invalid_base_does_not_get_silently_repaired(self):
        for mutate in (lambda x: x.update(unrecognized=True), lambda x: x["budget"].update(max_paid_cost_usd=1)):
            base = deepcopy(self.base)
            mutate(base)
            with self.assertRaises(PipelineError):
                compile_brief("clear resin", base)

    def test_unsupported_priority_preserves_clarification_issues(self):
        result = self.assert_blocked("make it prettier; add a dragon; cup.height=1.7; cup.height=1.8", "unsupported")
        self.assertEqual(len(result["issues"]), 3)
        self.assertEqual({issue["kind"] for issue in result["issues"]}, {"unsupported", "needs_clarification"})

    def test_complete_defaults_and_provenance(self):
        result = self.compile("clear resin; samples=16")
        self.assertEqual(result["provenance"]["render.samples"], {"source": "explicit_numeric", "clause_indexes": [2]})
        self.assertEqual(result["provenance"]["liquid.cloudiness"]["source"], "phrase_default")
        self.assertEqual(result["provenance"]["cameras.hero.position"]["source"], "base")
        self.assertEqual(result["defaults"]["render.seed"], 42)
        self.assertNotIn("render.samples", result["defaults"])
        self.assertNotIn("brief", result["defaults"])
        self.assertEqual(result["provenance"]["brief"]["source"], "original_brief")
        self.assertEqual(set(result["provenance"]), set(result["defaults"]) | set(result["requested_parameters"]) | {"brief"})

    def test_base_digest_and_input_immutability(self):
        before = deepcopy(self.base)
        first = self.compile("samples=16")
        second = self.compile("samples=16")
        self.assertEqual(self.base, before)
        self.assertEqual(first, second)
        digest = hashlib.sha256(json.dumps(self.base, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        self.assertEqual(first["base"]["sha256"], digest)
        first["spec"]["cameras"]["hero"]["position"][0] = 99
        self.assertEqual(self.base, before)

    def test_no_renderer_or_external_service_invoked(self):
        with patch("subprocess.run", side_effect=AssertionError("Must not render")), patch("subprocess.Popen", side_effect=AssertionError("Must not execute")):
            self.assertEqual(self.compile(ENGLISH)["status"], "compiled")

    def test_result_schema_is_current_and_json_serializable(self):
        schema = read_json(ROOT / "schemas" / "brief-result.schema.json")
        for text in (ENGLISH, "samples=NaN", "add a dragon"):
            result = self.compile(text)
            json.dumps(result, allow_nan=False)
            self.assertEqual(set(schema["required"]), set(result))
            try:
                import jsonschema
            except ImportError:
                continue  # This project has no mandatory JSON Schema dependency.
            jsonschema.Draft202012Validator(schema).validate(result)


class BriefCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "cgstudio.brief", *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=10)

    def test_help_and_describe(self):
        result = self.cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("describe", result.stdout)
        result = self.cli("describe")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cup.height", json.loads(result.stdout)["parameters"])

    def test_compile_report_and_runnable_spec(self):
        report, spec = self.folder / "report.json", self.folder / "spec.json"
        result = self.cli("compile", "--brief", ENGLISH, "--output", report, "--spec-output", spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_json(report)["spec"], read_json(spec))
        validate_spec(read_json(spec))
        validate = subprocess.run([sys.executable, "-m", "cgstudio", "validate", "--spec", str(spec)], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_japanese_file_and_explicit_base(self):
        brief = self.folder / "brief.txt"
        brief.write_text(JAPANESE, encoding="utf-8")
        result = self.cli("compile", "--brief-file", brief, "--base", DEFAULT_BASE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["brief"], JAPANESE)

    def test_failed_compile_has_report_but_no_spec(self):
        report, spec = self.folder / "report.json", self.folder / "spec.json"
        result = self.cli("compile", "--brief", "add a dragon", "--output", report, "--spec-output", spec)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(read_json(report)["status"], "unsupported")
        self.assertIsNone(read_json(report)["spec"])
        self.assertFalse(spec.exists())

    def test_never_overwrites_evidence(self):
        report = self.folder / "old-report.json"
        report.write_text("retain me")
        result = self.cli("compile", "--brief", "samples=16", "--output", report)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report.read_text(), "retain me")

    def test_base_cannot_be_overwritten(self):
        base = self.folder / "base.json"
        base.write_bytes(DEFAULT_BASE.read_bytes())
        original = base.read_bytes()
        result = self.cli("compile", "--brief", "samples=16", "--base", base, "--spec-output", base)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(base.read_bytes(), original)

    def test_reports_and_spec_cannot_share_target(self):
        output = self.folder / "same.json"
        result = self.cli("compile", "--brief", "samples=16", "--output", output, "--spec-output", output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_missing_and_invalid_inputs(self):
        for args in (("--brief-file", self.folder / "missing.txt"), ("--brief", "samples=16", "--base", self.folder / "missing.json")):
            with self.subTest(args=args):
                result = self.cli("compile", *args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)["status"], "error")


if __name__ == "__main__":
    unittest.main()
