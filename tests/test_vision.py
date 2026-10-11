"""Explicit test doubles only: no live model, optical judgment or API calls."""
from copy import deepcopy
import base64
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cgstudio.auto import run_unattended
from cgstudio.io import PipelineError, read_json, sha256_file, write_json
from cgstudio.pipeline import ROOT, load_state, start_run
from cgstudio.vision import (LocalVisionProvider, PROTOCOL, ProviderFailure, RESPONSE_SCHEMA,
                             ReviewLimits, _bounded_stdio, prepare_request, validate_response)

# A provider fixture produces schema data; it has no image understanding.
FIXTURE_PROVIDER = r'''
import json, sys, time, subprocess
q = json.load(sys.stdin)
mode = sys.argv[1]
if mode == 'timeout':
    time.sleep(10)
if mode == 'oversize':
    sys.stdout.write('x' * 300000); sys.exit(0)
if mode == 'stderr_oversize':
    sys.stderr.write('x' * 70000); sys.exit(0)
if mode == 'exit':
    sys.exit(17)
if mode == 'duplicate':
    print('{"protocol":"bad","protocol":"bad"}'); sys.exit(0)
if mode == 'malformed':
    print('```json\n{}\n```'); sys.exit(0)
r = q['review_template']
r['status'] = 'accepted'
r['summary'] = 'TEST DOUBLE ONLY: synthetic protocol fixture; no visual judgment.'
r['reviewer'] = {'name': q['provider_id'], 'kind': 'vision_model', 'image_inspected': True,
                 'inspected_cameras': ['hero', 'side', 'top']}
if mode == 'revise' and r['iteration'] == 1:
    r['status'] = 'revise'
    r['issues'] = [{'priority': 'P1', 'category': 'material', 'observation': 'hero: TEST DOUBLE fixture issue.',
                    'requested_change': 'TEST DOUBLE numeric fixture change.'}]
    r['approved_parameter_patch'] = {'liquid.roughness': 0.08}
if mode == 'always_revise':
    r['status'] = 'revise'
    r['issues'] = [{'priority': 'P1', 'category': 'material', 'observation': 'hero: TEST DOUBLE fixture issue.',
                    'requested_change': 'TEST DOUBLE numeric fixture change.'}]
    r['approved_parameter_patch'] = {'liquid.roughness': 0.07 + r['iteration'] * 0.01}
x = {'protocol': q['protocol'], 'provider_id': q['provider_id'], 'request_id': q['request_id'],
     'review': r, 'usage': {'paid_cost_usd': 0},
     'references_sha256': [{'label': ref['label'], 'sha256': ref['sha256']} for ref in q['reference_images']]}
if mode == 'paid':
    x['usage']['paid_cost_usd'] = 0.01
if mode == 'bad_hash':
    r['images_sha256']['top'] = 'a' * 64
if mode == 'uninspected':
    r['reviewer']['image_inspected'] = False
if mode == 'unknown':
    x['python'] = '__import__("os").system("false")'
if mode == 'wrong_request':
    x['request_id'] = '0' * 36
if mode == 'wrong_provider':
    x['provider_id'] = 'other-provider'
if mode == 'bad_label':
    r['summary'] = 'Visually accepted.'
print(json.dumps(x))
'''


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.output = self.folder / 'run'
        self.spec = read_json(ROOT / 'specs' / 'clear_resin.json')
        self.spec['render'].update(width=64, height=64, samples=1)
        self.spec_path = self.folder / 'spec.json'
        write_json(self.spec_path, self.spec)
        self.state = start_run(self.spec_path, self.output, str(ROOT / 'tests' / 'fake_blender.py'))
        self.fixture = self.folder / 'provider.py'
        self.fixture.write_text(FIXTURE_PROVIDER)
        self.provider = self.make_provider('accept')

    def make_provider(self, mode):
        return LocalVisionProvider('TEST-DOUBLE-fixture', (sys.executable, str(self.fixture), mode), 'test_double')

    def run_adapter(self, mode='accept', **kwargs):
        return run_unattended(self.output, self.make_provider(mode), blender=str(ROOT / 'tests' / 'fake_blender.py'),
                              test_fixture_only=True, **kwargs)

    def request(self):
        request = prepare_request(self.output, self.state, test_fixture_only=True)
        request['provider_id'] = self.provider.provider_id
        return request

    def response(self):
        request = self.request()
        return request, self.provider.invoke(request, 1)

    def update_manifest(self, camera, changes):
        state = load_state(self.output)
        target = self.output / state['iterations'][-1]['directory']
        path = target / f'manifest_{camera}.json'
        manifest = read_json(path)
        manifest.update(changes)
        write_json(path, manifest)
        state['iterations'][-1]['artifact_sha256'][path.name] = sha256_file(path)
        write_json(self.output / 'state.json', state)
        self.state = state

    def test_no_provider_is_pending_without_execution_or_ledger(self):
        before = (self.output / 'state.json').read_bytes()
        result = run_unattended(self.output)
        self.assertEqual(result['pipeline']['status'], 'review_pending')
        self.assertEqual(result['adapter']['calls'], 0)
        self.assertEqual(before, (self.output / 'state.json').read_bytes())
        self.assertFalse((self.output / 'vision_ledger.json').exists())

    def test_request_contains_actual_three_png_bytes_and_frozen_cameras(self):
        request = self.request()
        self.assertEqual([i['camera'] for i in request['images']], ['hero', 'side', 'top'])
        for image in request['images']:
            self.assertEqual(base64.b64decode(image['base64']), (self.output / 'iteration_001' / (image['camera'] + '.png')).read_bytes())
            self.assertEqual(image['camera_parameters'], self.spec['cameras'][image['camera']])
        self.assertEqual(request['scope'], 'test_double_only')

    def test_fixture_can_accept_only_with_explicit_nonvisual_label(self):
        result = self.run_adapter()
        self.assertEqual(result['pipeline']['status'], 'accepted')
        self.assertEqual(result['adapter']['scope'], 'test_double_only')
        ledger = read_json(self.output / 'vision_ledger.json')
        self.assertEqual(len(ledger['attempts']), 1)
        review = read_json(self.output / ledger['attempts'][0]['review_file'])
        self.assertTrue(review['summary'].startswith('TEST DOUBLE ONLY:'))
        self.assertEqual(ledger['attempts'][0]['paid_cost_usd'], 0)

    def test_fixture_revision_runs_real_protocol_without_camera_seed_change(self):
        result = self.run_adapter('revise')
        self.assertEqual(result['pipeline']['status'], 'accepted')
        self.assertEqual(result['pipeline']['render_attempts'], 2)
        revised = read_json(self.output / 'iteration_002' / 'spec.json')
        self.assertEqual(revised['liquid']['roughness'], 0.08)
        self.assertEqual(revised['cameras'], self.spec['cameras'])
        self.assertEqual(revised['render']['seed'], self.spec['render']['seed'])
        self.assertEqual(revised['budget'], self.spec['budget'])

    def test_third_revision_exhausts_original_render_budget(self):
        result = self.run_adapter('always_revise')
        self.assertEqual(result['pipeline']['status'], 'budget_exhausted')
        self.assertEqual(result['pipeline']['render_attempts'], 3)
        self.assertFalse((self.output / 'iteration_004').exists())

    def test_malformed_untrusted_outputs_fail_closed_and_retry_is_bounded(self):
        for mode in ('malformed', 'duplicate', 'unknown', 'bad_hash', 'uninspected', 'paid', 'wrong_request', 'wrong_provider', 'bad_label'):
            with self.subTest(mode=mode):
                request = self.request()
                provider = self.make_provider(mode)
                with self.assertRaises(PipelineError):
                    response = provider.invoke(request, 1)
                    validate_response(response, request, provider, self.state, ReviewLimits())
        result = self.run_adapter('malformed')
        self.assertEqual(result['pipeline']['status'], 'review_pending')
        self.assertEqual(result['adapter']['calls'], 2)
        rerun = self.run_adapter('malformed')
        self.assertEqual(rerun['adapter']['calls'], 2)
        self.assertFalse(load_state(self.output)['iterations'][0]['multiview_validated'])

    def test_timeout_kills_and_remains_pending(self):
        before = load_state(self.output)['active_seconds']
        started = time.monotonic()
        result = self.run_adapter('timeout', limits=ReviewLimits(per_call_seconds=0.08, total_seconds=0.12))
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(result['pipeline']['status'], 'review_pending')
        self.assertGreater(result['pipeline']['active_seconds'], before + 0.1)
        self.assertLessEqual(result['adapter']['calls'], 2)

    def test_provider_cannot_exceed_remaining_pipeline_time(self):
        state = load_state(self.output)
        state['active_seconds'] = state['limits']['total_seconds'] - 0.06
        write_json(self.output / 'state.json', state)
        result = self.run_adapter('timeout')
        ledger = read_json(self.output / 'vision_ledger.json')
        self.assertLessEqual(ledger['attempts'][0]['timeout_seconds'], 0.061)
        self.assertEqual(result['adapter']['calls'], 1)
        self.assertEqual(result['pipeline']['status'], 'review_pending')

    def test_oversized_stdout_stderr_nonzero_exit_are_bounded(self):
        for mode in ('oversize', 'stderr_oversize', 'exit'):
            with self.subTest(mode=mode), self.assertRaises(ProviderFailure):
                self.make_provider(mode).invoke(self.request(), 1)

    def test_provider_cannot_wait_forever_without_reading_stdin(self):
        with self.assertRaisesRegex(ProviderFailure, 'deadline'):
            _bounded_stdio((sys.executable, '-c', 'import time; time.sleep(10)'), {'x': 'y' * 1000000}, 0.05)

    @unittest.skipUnless(os.name == 'posix', 'process groups required')
    def test_provider_descendants_are_killed_on_timeout(self):
        marker = self.folder / 'survived'
        child = f'import time,pathlib; time.sleep(0.5); pathlib.Path({str(marker)!r}).write_text("leak")'
        parent = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(10)'
        with self.assertRaises(ProviderFailure):
            _bounded_stdio((sys.executable, '-c', parent), {}, 0.08)
        time.sleep(0.55)
        self.assertFalse(marker.exists())

    def test_zero_cost_is_enforced_before_launch_and_in_response(self):
        for amount in (0.01, True, float('nan')):
            with self.subTest(amount=amount), self.assertRaises(PipelineError):
                LocalVisionProvider('bad', (sys.executable,), declared_max_cost_usd=amount)
        for kwargs in ({'max_paid_cost_usd': 1}, {'max_calls': 7}, {'attempts_per_iteration': 3}, {'per_call_seconds': 61},
                       {'total_seconds': float('inf')}, {'max_patch_parameters': 4}, {'max_issues': 7}):
            with self.subTest(kwargs=kwargs), self.assertRaises(PipelineError):
                ReviewLimits(**kwargs)

    def test_unknown_config_and_credentials_are_not_accepted(self):
        path = self.folder / 'config.json'
        config = self.provider.config()
        config['api_key'] = 'not-a-real-key'
        write_json(path, config)
        with self.assertRaises(PipelineError):
            LocalVisionProvider.from_file(path)
        with self.assertRaises(PipelineError):
            LocalVisionProvider('bad', ('python',))

    def test_fixture_mode_is_explicit_and_cannot_certify_production(self):
        with self.assertRaises(PipelineError):
            run_unattended(self.output, self.provider)
        with self.assertRaises(PipelineError):
            prepare_request(self.output, self.state)
        self.update_manifest('side', {'test_fixture': False})
        with self.assertRaisesRegex(PipelineError, 'cannot be mixed'):
            self.request()

    def test_camera_and_frame_alignment_is_required(self):
        self.update_manifest('side', {'camera': 'hero'})
        with self.assertRaisesRegex(PipelineError, 'alignment'):
            self.request()
        self.update_manifest('side', {'camera': 'side', 'frame': 19})
        with self.assertRaisesRegex(PipelineError, 'alignment'):
            self.request()

    def test_real_manifest_contract_binds_full_spec_and_render_settings(self):
        state = self.state
        entry = state['iterations'][0]
        for camera in ('hero', 'side', 'top'):
            self.update_manifest(camera, {'test_fixture': False, 'spec': self.spec,
                                         'spec_file_sha256': entry['spec_sha256'], 'builder_sha256': entry['builder_sha256'],
                                         **{key: self.spec['render'][key] for key in ('engine','device','samples','seed','denoise')}})
        request = prepare_request(self.output, self.state)
        self.assertEqual(request['scope'], 'three_view_still_look_only')
        self.update_manifest('side', {'seed': 0})
        with self.assertRaisesRegex(PipelineError, 'alignment'):
            prepare_request(self.output, self.state)

    def test_changed_images_and_builder_fail_before_provider(self):
        path = self.output / 'iteration_001' / 'top.png'
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(PipelineError, 'evidence changed'):
            self.run_adapter()
        self.assertFalse((self.output / 'vision_ledger.json').exists())

    def test_priority_and_patch_bounds_and_programmatic_safety(self):
        request, response = self.response()
        response['review']['status'] = 'revise'
        response['review']['issues'] = [{'priority': 'P1', 'category': 'material', 'observation': 'hero: TEST fixture', 'requested_change': 'Fixture change'}]
        for values in ({'code': 'exec(1)'}, {'cameras.hero.position': 5}, {'budget.max_iterations': 4},
                       {'liquid.roughness': True}, {'liquid.roughness': float('nan')}, {'render.samples': 3.5},
                       {'liquid.roughness': self.spec['liquid']['roughness']},
                       {'cup.roughness': 0.1, 'cup.ior': 1.5, 'liquid.roughness': 0.1, 'liquid.ior': 1.5}):
            with self.subTest(values=values), self.assertRaises(PipelineError):
                bad = deepcopy(response)
                bad['review']['approved_parameter_patch'] = values
                validate_response(bad, request, self.provider, self.state, ReviewLimits())
        response['review']['approved_parameter_patch'] = {'liquid.roughness': 0.08}
        response['review']['issues'][0]['observation'] = 'Looks wrong somewhere'
        with self.assertRaisesRegex(PipelineError, 'identify'):
            validate_response(response, request, self.provider, self.state, ReviewLimits())

    def test_numeric_patch_must_fit_fixed_offcenter_stream_geometry(self):
        spec = deepcopy(self.spec)
        spec['cup']['outer_radius'] = 0.5
        path = self.folder / 'small-spec.json'
        write_json(path, spec)
        output = self.folder / 'small-run'
        state = start_run(path, output, str(ROOT / 'tests' / 'fake_blender.py'))
        request = prepare_request(output, state, test_fixture_only=True)
        request['provider_id'] = self.provider.provider_id
        response = self.provider.invoke(request, 1)
        response['review']['status'] = 'revise'
        response['review']['issues'] = [{'priority': 'P1', 'category': 'geometry', 'observation': 'hero: TEST DOUBLE stream fixture', 'requested_change': 'TEST DOUBLE widening'}]
        response['review']['approved_parameter_patch'] = {'liquid.stream_radius': 0.3}
        with self.assertRaisesRegex(PipelineError, 'off-center stream'):
            validate_response(response, request, self.provider, state, ReviewLimits())

    def test_unsorted_priorities_and_too_many_issues_rejected(self):
        request, response = self.response()
        issue = {'priority': 'P2', 'category': 'material', 'observation': 'hero: fixture', 'requested_change': 'Fixture'}
        response['review']['issues'] = [issue] * 7
        with self.assertRaisesRegex(PipelineError, 'too many issues'):
            validate_response(response, request, self.provider, self.state, ReviewLimits())
        response['review']['issues'] = [dict(issue, priority='P3'), issue]
        with self.assertRaisesRegex(PipelineError, 'sort issues'):
            validate_response(response, request, self.provider, self.state, ReviewLimits())

    def test_cannot_reset_attempts_by_changing_provider_or_limits(self):
        self.run_adapter('malformed')
        with self.assertRaisesRegex(PipelineError, 'cannot be changed'):
            self.run_adapter('accept')
        with self.assertRaisesRegex(PipelineError, 'cannot be changed'):
            self.run_adapter('malformed', limits=ReviewLimits(max_calls=1))

    def test_interrupted_attempt_blocks_reexecution(self):
        self.run_adapter('malformed')
        ledger = read_json(self.output / 'vision_ledger.json')
        ledger['attempts'][0]['status'] = 'started'
        write_json(self.output / 'vision_ledger.json', ledger)
        result = self.run_adapter('malformed')
        self.assertIn('uncertain', result['adapter']['reason'])
        self.assertEqual(result['adapter']['calls'], 2)

    def test_optional_reference_bytes_hashes_and_response_binding(self):
        path = self.output / 'iteration_001' / 'hero.png'
        refs = [{'label': 'fixture-reference', 'sha256': sha256_file(path), 'path': str(path), 'source_url': 'https://example.invalid/test-fixture'}]
        request = prepare_request(self.output, self.state, test_fixture_only=True, references=refs)
        request['provider_id'] = self.provider.provider_id
        self.assertEqual(base64.b64decode(request['reference_images'][0]['base64']), path.read_bytes())
        response = self.provider.invoke(request, 1)
        validate_response(response, request, self.provider, self.state, ReviewLimits())
        response['references_sha256'] = []
        with self.assertRaisesRegex(PipelineError, 'reference image'):
            validate_response(response, request, self.provider, self.state, ReviewLimits())
        result = self.run_adapter(references=refs)
        self.assertEqual(result['pipeline']['status'], 'accepted')

    def test_reference_tamper_duplicate_and_unknown_fields_fail_closed(self):
        path = self.output / 'iteration_001' / 'hero.png'
        reference = {'label': 'fixture', 'sha256': sha256_file(path), 'path': str(path), 'source_url': 'https://example.invalid/fixture'}
        for refs in ([dict(reference, sha256='0' * 64)], [reference, reference], [dict(reference, command='evil')]):
            with self.subTest(refs=refs), self.assertRaises(PipelineError):
                prepare_request(self.output, self.state, test_fixture_only=True, references=refs)

    def test_saved_schema_matches_runtime_contract(self):
        self.assertEqual(read_json(ROOT / 'schemas' / 'vision-response.schema.json'), RESPONSE_SCHEMA)

    def test_cli_missing_configuration_reports_pending_honestly(self):
        result = subprocess.run([sys.executable, '-m', 'cgstudio.auto', '--output', str(self.output)], cwd=ROOT, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response['pipeline']['status'], 'review_pending')
        self.assertEqual(response['adapter']['provider_id'], None)


if __name__ == '__main__':
    unittest.main()
