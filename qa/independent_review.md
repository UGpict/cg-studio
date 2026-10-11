# Independent CG Studio review

## Decision

**Working prototype; final beauty shot not accepted.** The real bounded review run reached terminal `rejected` after exactly three three-view render iterations and the decisions `revise`, `revise`, `rejected`. Active execution was 513.321 seconds, with $0 paid-service spend. No fourth look attempt was requested.

## Actual visual evidence

The reviewer inspected actual pixels for the original baseline, intermediate hero, all nine raw gated renders, all three final color-only OIDN renders, the separate raw/OIDN hero comparison, and all 36 frames of the earlier-look motion preview in native-size frame sheets. No photographic reference was supplied or inspected; reference-image agreement is not claimed.

- Improved: finite cup wall/rim/base readability; shaped metal reflections and grounded support; cleaner edges after sampling and OIDN; reduced broad pale wash in the final lower fill.
- **P1 · MaterialLighting:** the final hero stream nearly disappears across a substantial middle section above the vessel. A continuous nozzle-to-impact pour is not reliably readable.
- P2 · MaterialLighting: the darker setup reduces pale wash but also suppresses wall/free-surface detail; side view retains dominant bright reflection patches.
- P2 · Render: raw renders remain grainy. Color-only OIDN suppresses grain while softening some thin transparent detail. No auxiliary albedo/normal passes or temporal denoising were used.
- P2 · Animation: the three-second preview demonstrates a rising fixed-topology fill, but uses the earlier iteration-002 look. Frame-sheet inspection does not establish flicker-free live playback or final-film quality.

Future visual acceptance requires legible continuous stream edges/reflections at all three approved views, a clear filled volume with a distinct free surface, and a final-look motion playback check. The final director decision remains with the project owner.

## Geometry and software evidence

- Saved final-scene measurements show zero non-manifold edges, positive signed volume, and finite coordinates for cup, liquid and stream. Nozzle bore radius 0.0978 clears stream top radius 0.0918. These tests do not prove all self-intersections or fluid physics.
- Independent execution of all 25 unit tests passed in 4.594 seconds; Python compilation passed. The tests use an explicitly labeled renderer test double. Actual Blender evidence is recorded separately.
- Tested controls include three-view hash binding, stale-review rejection, no acceptance of an uninspected review, bounded numeric patches, iteration/expense limits, process-group timeout cleanup, and no silent run overwrite.
- The explicit review-file adapter is implemented. An unattended vision/API adapter is unconfigured. Numeric image measurements are descriptive, not aesthetic scores.
- The motion helper now uses process-group cleanup; the earlier full preview completed successfully before that watchdog-only correction.
- Current code freezes a builder snapshot and records its hash for future iterations. The completed real run predates that addition, so the comparisons are labeled look-development revisions rather than a one-variable benchmark.

## A/B/C truth boundary

- A, conventional Three.js: implemented; browser rendering **not run** because Chromium was blocked before page load by socket EPERM.
- B, Blender Cycles: real Blender 4.3.2 CPU renders and review/revision execution completed. No GPU claim.
- C, Blender GLB to Three.js: actual GLTFLoader parsing passed, including transmission, IOR and volume. Cup and stream thickness export hints were corrected. Browser appearance/performance **not run** under the same Chromium blocker.

No A/B/C optical equivalence, real-time performance, fluid simulation, automated visual acceptance, or reference-photo agreement is asserted.

## Review artifacts

- `final_visual_review.json`: final prioritized findings, owners, acceptance checks, and six raw/denoised image hashes
- `gated_review_iteration_001.json`, `gated_review_iteration_002.json`, `gated_review_iteration_003.json`: actual-pixel reviews consumed by the gate
- `software_audit.json`, `independent_tests.log`: execution/claim audit
- `denoising_review.json`, `motion_review.json`: separate cleanup and animation limitations
