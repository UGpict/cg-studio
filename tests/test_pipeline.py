from __future__ import annotations
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cgstudio.budget import BudgetExceeded, Limits, run_renderer
from cgstudio.io import PipelineError, read_json, write_json
from cgstudio.pipeline import ARTIFACTS, ROOT, load_state, renderer_command, resume_run, run_lock, start_run
from cgstudio.review import apply_patch, validate_review
from cgstudio.spec import PATCH_ALLOWLIST, validate_spec

FAKE_BLENDER = str(ROOT / 'tests' / 'fake_blender.py')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.spec = read_json(ROOT / 'specs' / 'clear_resin.json')
        self.spec['render'].update(width=64, height=64, samples=1)
        self.spec_path = self.folder / 'spec.json'
        self.output = self.folder / 'run'
        write_json(self.spec_path, self.spec)

    def run_fixture(self, **kwargs):
        return start_run(self.spec_path, self.output, FAKE_BLENDER, **kwargs)

    def completed_review(self, state, status='accepted', patch_values=None):
        entry = state['iterations'][-1]
        review = read_json(self.output / entry['directory'] / 'review.template.json')
        review.update(status=status, summary='TEST fixture review; no production image acceptance.')
        review['reviewer'].update(name='Test-only fixture reviewer', image_inspected=True,
                                   inspected_cameras=['hero', 'side', 'top'])
        if status in ('revise', 'rejected'):
            review['issues'] = [{'priority': 'P1', 'category': 'material', 'observation': 'Test-only issue', 'requested_change': 'Test-only adjustment'}]
        if patch_values:
            review['approved_parameter_patch'] = patch_values
        return review

    def save_review(self, review):
        path = self.folder / 'review.json'
        write_json(path, review)
        return path

    def test_spec_validates_actual_example(self):
        self.assertIs(validate_spec(self.spec), self.spec)

    def test_spec_rejects_unknown_nonfinite_boolean_and_geometry(self):
        for group, key, value in [('render', 'samples', True), ('liquid', 'roughness', float('nan')),
                                   ('cup', 'wall_thickness', 0.5), ('budget', 'max_paid_cost_usd', 1)]:
            with self.subTest(group=group, key=key):
                spec = deepcopy(self.spec)
                spec[group][key] = value
                if key == 'wall_thickness':
                    spec['cup']['outer_radius'] = 0.2
                with self.assertRaises(PipelineError):
                    validate_spec(spec)
        spec = deepcopy(self.spec)
        spec['code'] = 'arbitrary code'
        with self.assertRaises(PipelineError):
            validate_spec(spec)

    def test_render_stops_pending_without_vision(self):
        state = self.run_fixture()
        self.assertEqual(state['status'], 'review_pending')
        self.assertEqual(len(state['iterations']), 1)
        entry = state['iterations'][0]
        self.assertFalse(entry['multiview_validated'])
        self.assertTrue(entry['multiview_rendered'])
        self.assertEqual(set(entry['images_sha256']), {'hero', 'side', 'top'})
        self.assertEqual(len(entry['renders']), 3)
        for artifact in ARTIFACTS:
            self.assertTrue((self.output / 'iteration_001' / artifact).exists())
        template = self.output / 'iteration_001' / 'review.template.json'
        with self.assertRaises(PipelineError):
            resume_run(self.output, template, FAKE_BLENDER)
        self.assertEqual(load_state(self.output)['status'], 'review_pending')
        metrics = read_json(self.output / 'iteration_001' / 'image_measurements.json')
        self.assertIsNone(metrics['hero']['quality_verdict'])

    def test_acceptance_requires_exact_evidence_then_stops(self):
        state = self.run_fixture()
        review = self.completed_review(state)
        accepted = resume_run(self.output, self.save_review(review), FAKE_BLENDER)
        self.assertEqual(accepted['status'], 'accepted')
        self.assertEqual(len(accepted['iterations']), 1)
        self.assertTrue(accepted['iterations'][0]['multiview_validated'])
        with self.assertRaises(PipelineError):
            resume_run(self.output, self.folder / 'review.json', FAKE_BLENDER)

    def test_reviews_cannot_replay_or_mismatch_hashes(self):
        state = self.run_fixture()
        entry = state['iterations'][0]
        for key, value in [('run_id', 'another-run'), ('iteration', 2), ('image_sha256', 'a' * 64), ('spec_sha256', 'b' * 64)]:
            with self.subTest(key=key):
                review = self.completed_review(state)
                review[key] = value
                with self.assertRaises(PipelineError):
                    validate_review(review, state['run_id'], entry)
        review = self.completed_review(state)
        review['images_sha256']['side'] = 'c' * 64
        with self.assertRaises(PipelineError):
            validate_review(review, state['run_id'], entry)
        review = self.completed_review(state)
        review['reviewer']['inspected_cameras'] = ['hero', 'hero', 'top']
        with self.assertRaises(PipelineError):
            validate_review(review, state['run_id'], entry)

    def test_uninspected_and_blocking_reviews_cannot_accept(self):
        state = self.run_fixture()
        for change in ('uninspected', 'blocking', 'fake_score'):
            review = self.completed_review(state)
            if change == 'uninspected':
                review['reviewer']['image_inspected'] = False
            elif change == 'blocking':
                review['issues'] = [{'priority': 'P1', 'category': 'geometry', 'observation': 'Broken', 'requested_change': 'Fix'}]
            else:
                review['quality_score'] = 9.9
            with self.assertRaises(PipelineError):
                resume_run(self.output, self.save_review(review), FAKE_BLENDER)

    def test_evidence_changed_after_render_cannot_accept(self):
        state = self.run_fixture()
        review = self.completed_review(state)
        (self.output / 'iteration_001' / 'top.png').write_bytes(b'changed')
        with self.assertRaisesRegex(PipelineError, 'evidence changed'):
            resume_run(self.output, self.save_review(review), FAKE_BLENDER)

    def test_spec_changed_after_render_cannot_accept(self):
        state = self.run_fixture()
        review = self.completed_review(state)
        (self.output / 'iteration_001' / 'spec.json').write_text('{}')
        with self.assertRaisesRegex(PipelineError, 'spec changed'):
            resume_run(self.output, self.save_review(review), FAKE_BLENDER)

    def test_revision_applies_only_approved_parameters(self):
        state = self.run_fixture()
        review = self.completed_review(state, 'revise', {'liquid.roughness': 0.08, 'render.samples': 2})
        revised = resume_run(self.output, self.save_review(review), FAKE_BLENDER)
        self.assertEqual(revised['status'], 'review_pending')
        self.assertEqual(len(revised['iterations']), 2)
        second = read_json(self.output / 'iteration_002' / 'spec.json')
        self.assertEqual(second['liquid']['roughness'], 0.08)
        self.assertEqual(second['cameras'], self.spec['cameras'])
        self.assertEqual(second['render']['seed'], self.spec['render']['seed'])
        self.assertEqual(second['budget'], self.spec['budget'])
        self.assertTrue(revised['iterations'][0]['review_sha256'])

    def test_patch_rejects_code_camera_budget_unknown_noop_and_bounds(self):
        for values in [{'cameras.hero.position': 1}, {'budget.max_iterations': 99}, {'code': 'exec()'},
                       {'liquid.roughness': 2}, {'liquid.roughness': True}, {'render.samples': 3.5},
                       {'liquid.roughness': self.spec['liquid']['roughness']}, {}]:
            with self.subTest(patch=values), self.assertRaises(PipelineError):
                apply_patch(self.spec, values)

    def test_three_iteration_ceiling_is_absolute(self):
        state = self.run_fixture()
        for value in (0.08, 0.09, 0.1):
            review = self.completed_review(state, 'revise', {'liquid.roughness': value})
            state = resume_run(self.output, self.save_review(review), FAKE_BLENDER)
        self.assertEqual(state['status'], 'budget_exhausted')
        self.assertEqual(len(state['iterations']), 3)
        self.assertFalse((self.output / 'iteration_004').exists())

    def test_rejected_review_is_terminal(self):
        state = self.run_fixture()
        review = self.completed_review(state, 'rejected')
        state = resume_run(self.output, self.save_review(review), FAKE_BLENDER)
        self.assertEqual(state['status'], 'rejected')
        self.assertEqual(len(state['iterations']), 1)

    def test_shorter_spec_budget_is_honored(self):
        self.spec['budget']['max_iterations'] = 1
        write_json(self.spec_path, self.spec)
        state = self.run_fixture()
        review = self.completed_review(state, 'revise', {'liquid.roughness': 0.08})
        state = resume_run(self.output, self.save_review(review), FAKE_BLENDER)
        self.assertEqual(state['status'], 'budget_exhausted')
        self.assertEqual(len(state['iterations']), 1)

    def test_cli_cannot_expand_spec_budget(self):
        self.spec['budget']['max_iterations'] = 1
        write_json(self.spec_path, self.spec)
        with self.assertRaises(PipelineError):
            self.run_fixture(limits=Limits())

    def test_renderer_failure_records_terminal_state(self):
        self.spec['project'] = 'test-renderer-failure'
        write_json(self.spec_path, self.spec)
        state = self.run_fixture()
        self.assertEqual(state['status'], 'failed')
        self.assertIn('17', state['iterations'][0]['error'])
        self.assertEqual(len(state['iterations'][0]['renders']), 1)

    def test_renderer_deadline_kills_and_does_not_start_next_camera(self):
        self.spec['project'] = 'test-timeout'
        write_json(self.spec_path, self.spec)
        started = time.monotonic()
        state = self.run_fixture(limits=Limits(3, 1, 0.1))
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(state['status'], 'budget_exhausted')
        self.assertEqual(len(state['iterations'][0]['renders']), 1)
        self.assertGreater(state['active_seconds'], 0.09)

    def test_total_budget_clips_renderer_timeout(self):
        self.spec['project'] = 'test-timeout'
        write_json(self.spec_path, self.spec)
        state = self.run_fixture(limits=Limits(3, 0.1, 180))
        self.assertEqual(state['status'], 'budget_exhausted')
        self.assertLessEqual(state['iterations'][0]['renders'][0]['timeout_seconds'], 0.1)

    def test_lock_blocks_concurrent_run(self):
        with run_lock(self.output):
            with self.assertRaisesRegex(PipelineError, 'already active'):
                self.run_fixture()

    def test_existing_run_cannot_be_overwritten(self):
        self.run_fixture()
        with self.assertRaises(PipelineError):
            self.run_fixture()

    def test_blender_command_keeps_arguments_separate(self):
        command = renderer_command('blender', Path('/tmp/space here/spec.json'), Path('/tmp/out path'), 18, 'side')
        self.assertIn('/tmp/space here/spec.json', command)
        self.assertEqual(command[-1], '--no-export')
        self.assertIn('side', command)

    def test_strict_json_rejects_duplicate_keys(self):
        path = self.folder / 'bad.json'
        path.write_text('{"status":"accepted","status":"revise"}')
        with self.assertRaises(PipelineError):
            read_json(path)

    def test_cli_validate_and_status(self):
        result = subprocess.run([sys.executable, '-m', 'cgstudio', 'validate', '--spec', str(self.spec_path)], cwd=ROOT, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.run_fixture()
        result = subprocess.run([sys.executable, '-m', 'cgstudio', 'status', '--output', str(self.output)], cwd=ROOT, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'review_pending')


class BudgetTests(unittest.TestCase):
    def test_limits_reject_expansion_and_paid_work(self):
        for kwargs in ({'max_iterations': 4}, {'max_iterations': True}, {'render_seconds': 181},
                       {'total_seconds': 1801}, {'paid_usd': 0.01}, {'paid_usd': False},
                       {'render_seconds': 0}, {'total_seconds': float('nan')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(PipelineError):
                Limits(**kwargs)

    def test_remaining_budget_is_minimum(self):
        self.assertEqual(Limits().render_timeout(1700), 100)
        with self.assertRaises(BudgetExceeded):
            Limits().render_timeout(1800)

    @unittest.skipUnless(os.name == 'posix', 'POSIX process groups required')
    def test_timeout_kills_descendant_processes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            marker = root / 'child-survived'
            child = f'import time,pathlib; time.sleep(0.6); pathlib.Path({str(marker)!r}).write_text("leaked")'
            parent = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(10)'
            with self.assertRaises(BudgetExceeded):
                run_renderer([sys.executable, '-c', parent], root / 'log', 0.15)
            time.sleep(0.65)
            self.assertFalse(marker.exists(), 'Timed-out renderer child process leaked')


if __name__ == '__main__':
    unittest.main()
