# CG Studio completion matrix

Updated 2026-10-11T13:35:45.231098+00:00. Overall: **in progress; not all complete**.

Supported resin-vessel scene family and bounded review/render workflow. Generic arbitrary-scene natural-language CG generation is not implemented or claimed.

## Phase 1 — 技術調査・設計
- Status: `complete_for_supported_MVP_scope`
- Verified: Primary-source stack/licensing/dependency research, B as offline master, A/C separate routes, strict bounded scene contract and role boundaries.
- Remaining: Keep design aligned with new compiler/adapter/browser evidence. This is a resin-vessel scene system, not a general arbitrary-scene generator.
- Completion check: Design states supported scene family, unsupported requests, optical approximations, budgets and the actual execution boundaries.
- Evidence: `docs/research-sources.md`, `docs/comparison-report.md`, `schemas/spec.schema.json`, `agents/README.md`

## Phase 2 — Blenderでの最小構成実装
- Status: `implemented_and_runtime_verified_for_supported_scene`
- Verified: Actual Blender 4.3.2 CPU scene build, thick closed vessel, resin surface/stream, materials/lights, fixed cameras and morph animation; final saved-scene geometry checks pass. A closed English/Japanese brief compiler is now implemented and independently exercised; renderer-specific profile constraints reject known invalid geometry. A fresh Japanese brief compiled and produced an actual 128x128, 8-sample Blender hero render in 2.925 seconds under a 60-second cap; smoke pixels were inspected.
- Remaining: The accepted visibility_v2 scene is integrated separately with its native scene and exact rendered source snapshot. Its evaluated Boolean animation/relative-IOR optics have no equivalent GLB export. Generic scene generation remains outside the implemented scope.
- Completion check: Supported Japanese/English briefs generate schema-valid bounded specs or explicit unsupported/ambiguous diagnostics; builder runs from the chosen final spec/source.
- Evidence: `scripts/build_scene.py`, `samples/resin_scene.blend`, `samples/resin_scene.glb`, `qa/scene_geometry_validation_final.json`, `cgstudio/brief.py`, `qa/visibility_v2/compiler_independent_probes.json`, `qa/brief_smoke/validation.json`

## Phase 3 — テストレンダリング
- Status: `accepted_still_scope_and_verified_motion_demo`
- Verified: MVP real three-view renders, raw/denoised comparisons, 36-frame earlier-look motion decode, all 36 frame pixels inspected in sheets. Visibility_v2 candidate 003 now passes actual raw/denoised three-angle still-readability review; earlier stream/interface blockers are resolved. Final-look 36-frame/384x384/12-fps/3-second MP4 decoded successfully; all 36 native-size frame pixels were independently inspected, with no obvious large union/silhouette pop.
- Remaining: Live perceptual video playback, flicker-free/full-resolution film quality, and equivalent GLB representation are not verified. The accepted offline scene uses renderer-specific relative-IOR interfaces and changing evaluated Boolean topology.
- Completion check: Chosen final scene passes actual three-angle still review and final-look playback review within stated samples/resolution/time limits.
- Evidence: `samples/`, `runs/gated/state.json`, `qa/final_visual_review.json`, `qa/motion_review.json`, `qa/visibility_v2/review_003.json`, `qa/visibility_v2/motion_review_003.json`, `experiments/visibility_v2/motion_003/validation.json`

## Phase 4 — 自動品質評価
- Status: `local_protocol_implemented_live_vision_unverified`
- Verified: Actual image-capable reviewer decisions, exact image/spec hashes, explicit issue priorities and reference-based qualitative criteria. Numeric measurements are not labeled as aesthetic scores. A local stdio vision protocol now attaches actual render/reference bytes and validates reference hash echoes; 26 protocol tests pass independently.
- Remaining: No local vision model/executable is configured and no live provider/model request or result has been verified. A bounded read-only check found no inference runtime or model weights in the checked cloud environment. This is a local protocol boundary, not an included external API client; model setup and actual image-dependent validation remain pending.
- Completion check: Actual render/reference image payloads reach an explicitly authorized available vision provider; schema-valid hash-bound findings return under retry/time/cost bounds. Missing setup remains blocked/pending, never auto-accepted.
- Evidence: `cgstudio/review.py`, `cgstudio/metrics.py`, `qa/gated_review_iteration_001.json`, `qa/gated_review_iteration_002.json`, `qa/gated_review_iteration_003.json`, `qa/visibility_v2/reference_evidence.json`, `cgstudio/vision.py`, `docs/brief-and-vision.md`, `qa/visibility_v2/extension_audit.json`, `qa/visibility_v2/local_vision_capability_audit.json`

## Phase 5 — 改善ループ実装
- Status: `bounded_review_file_loop_verified_unattended_end_to_end_open`
- Verified: Three actual iterations consumed revise→revise→rejected and stopped. 25 independent unit tests pass. Allowlist, hash binding, timeout process-group cleanup and expense/iteration caps are enforced. New unattended state-machine integration is covered by explicit test doubles, including original render-budget and persisted review-budget exhaustion.
- Remaining: Live image-provider review→render→review remains unverified; no test-double acceptance is production visual approval.
- Completion check: At least one actual automatic review→approved change→new render→new review chain is verified, plus acceptance/exhaustion/blocked terminal paths, without silent scope or budget expansion.
- Evidence: `cgstudio/pipeline.py`, `cgstudio/budget.py`, `qa/independent_tests.log`, `runs/gated/state.json`

## Phase 6 — Three.js移植検証
- Status: `asset_import_verified_browser_rendering_blocked`
- Verified: A/C implemented, real GLTFLoader parses the exported asset and optical extensions. Earlier local Chromium failed before page load with socket EPERM. Node execution of the actual viewer pose-selection block now selects both clips at hero time 1.5 seconds and matches frame-18 liquid/stream bounds; materials and all camera parameters remain unchanged.
- Remaining: Both local Chromium launch and the legitimate supported cloud browser route were blocked. No actual A/C rendered pixels, timings or playback exist. Morph-state import correction is verified only through actual GLTFLoader/evaluated-geometry Node execution.
- Completion check: Render A/C matched views in a legitimate working browser, inspect optical differences and animation, record actual renderer/backend/timing, and avoid claiming Cycles parity.
- Evidence: `web/viewer.js`, `scripts/capture_web.mjs`, `web/results/glb_validation.json`, `web/results/benchmark.json`, `qa/browser_validation/import_audit.json`, `qa/browser_validation/pose_test_result.json`

## Phase 7 — リファクタリング・ドキュメント整備
- Status: `local_integration_verified_remote_import_blocked`
- Verified: CLI, schemas, role contracts, beginner-oriented commands, renderer notes, comparisons, limitations and sample assets exist; Python compilation and 25 unit tests passed. Independent final full suite passes 103 tests (52 compiler, 26 vision, 25 existing); new documentation separates protocol tests from live model evidence. Reviewed extensions and the separate offline prototype are integrated locally with curated source/assets; full integrated tests pass 103 and Node hero-pose regression passes. A clean Git bundle and a user-authenticated, non-force draft-PR-branch publication helper are supplied.
- Remaining: The complete local revision is not on GitHub. At 2026-10-11 13:30 UTC, main remains README-only and draft PR #1 adds only .gitignore and pyproject.toml. A tiny connector commit request returned a cancellation error; no branch update followed and writes are paused. Manual helper live push is untested. Browser rendering and a live vision model remain open.
- Completion check: Final committed/published revision, reproducible fresh setup, accurate tested/blocked status, complete assets and direct beginner instructions are verified.
- Evidence: `README.md`, `docs/`, `agents/`, `schemas/`, `tests/`, `qa/independent_review.md`, `docs/manual-publication.md`, `qa/integrated_tests.log`, `experiments/visibility_v2/README.md`

## Reference-grounded criteria

Two actual [ArtResin tutorial images](https://www.artresin.com/blogs/artresin/artresin-101-how-to-artresin) were inspected for qualitative stream, transmission and contact cues. No calibrated optical constants, exact photographic match or motion behavior are inferred. Source URLs and hashes are in `reference_evidence.json`; cached photographs are excluded from this package.

## Final acceptance

The project director owns final visual and project acceptance. Implemented, tested, visually accepted, live-provider verified, browser verified and published are separate states. Software test fixtures and valid JSON cannot establish production visual quality. Missing provider configuration remains pending.
