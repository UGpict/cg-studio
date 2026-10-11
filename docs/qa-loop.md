# A bounded render–review–revise loop

This is executable local orchestration, with an explicit external visual-review gate. An optional local stdio vision-provider adapter and bounded unattended coordinator are available in `cgstudio.vision` and `cgstudio.auto`; see [brief-and-vision.md](brief-and-vision.md). No real model/provider is configured, and no live autonomous model review has run. The ordinary review-file workflow remains the default. A missing reviewer leaves the run at `review_pending`, never at `accepted`. Deterministic image measurements are diagnostic evidence, not visual-quality scores.

## Quick start

Run from this checkout with Python 3.10+ and a working local Blender installation:

```bash
python -m cgstudio validate --spec specs/clear_resin.json
python -m cgstudio run --spec specs/clear_resin.json --output runs/demo
python -m cgstudio status --output runs/demo
```

Use `--blender /absolute/path/to/blender` if Blender is not on PATH. No Python packages are required for orchestration. Optional Pillow adds decoded-pixel measurements. Blender runs CPU Cycles with four threads; the scene script and spec choose sample count and image dimensions. The source checkout includes the scene script and specs; the Python wheel alone is not a complete scene asset distribution.

A successful first run creates `runs/demo/iteration_001/hero.png`, `side.png`, `top.png`, the native `.blend`, a `.glb`, per-camera manifests, a spec snapshot, logs, measurements, and a review template. It stops for review.

## Real visual review is required

1. Open all three rendered PNGs and inspect actual pixels against the immutable spec snapshot and `qa/acceptance_criteria.md`. Inspect native/GLB animation separately if accepting animation or export claims. Still-image acceptance does not certify the full animation or WebGL fidelity.
2. Copy `review.template.json` to a new review JSON file. Keep its run ID, iteration, spec hash, hero hash, and three-camera hashes unchanged.
3. Fill `reviewer.name` and `reviewer.kind` (`human` or `vision_model`). Set `image_inspected` to `true` only after actual image inspection, and list `hero`, `side`, and `top` in `inspected_cameras`.
4. Write concrete, view-grounded observations and requested changes. Choose `accepted`, `revise`, or `rejected`.
5. Resume:

```bash
python -m cgstudio resume --output runs/demo --review /path/to/completed-review.json
```

There is no automatic trust proof that a person or model looked at pixels. The gate enforces a structured attestation and exact evidence identity. The external reviewer is the trust boundary. Never fill the attestation from filenames, measurements, or a render log alone. No review or score is fabricated by the orchestrator.

### Decisions

- `accepted`: no unresolved P0/P1 issues and no patch. The pipeline stops with the accepted iteration and image hash. This means the external reviewer accepted the supplied three still images under the stated scope.
- `revise`: at least one issue and a nonempty, genuinely changing numeric patch. The patch is applied to a copied spec, validated, saved, and used to render the next three-view iteration. Nothing is accepted implicitly.
- `rejected`: at least one issue, no patch. The pipeline stops without rendering again.
- `pending` exists only in unfinished templates and is intentionally invalid as a completed review.

The completed-review contract is documented in `schemas/review.schema.json`; runtime validation also enforces cross-field invariants. Extra fields, including invented `quality_score` fields, are rejected. Reviews for another run/iteration or changed evidence are rejected before run-state mutation. The image, native artifact, GLB, spec snapshot, and manifests are checked for changes before acceptance/resumption. A completed review is copied to the iteration with a SHA-256 audit digest.

### Issue priorities

- P0: unusable output, corrupted artifact, or critical evidence/brief failure
- P1: material visual defect or missing required cue; must resolve before acceptance
- P2: visible improvement that does not block the reviewer's stated scope
- P3: polish or minor inconsistency

Categories are geometry, material, lighting, composition, animation, export, or other. A review observation should identify the view and visible evidence, e.g. “Side view: the stream vanishes against the white card near the vessel rim.” Proposed changes are hypotheses to test, not guaranteed improvements.

## Narrow parameter feedback

Only these numeric dot paths can change through a review:

- `cup.roughness`, `cup.ior`
- `liquid.roughness`, `liquid.ior`, `liquid.transmission`, `liquid.absorption_density`, `liquid.cloudiness`, `liquid.meniscus_height`, `liquid.stream_radius`
- `lighting.key_energy`, `lighting.fill_energy`, `lighting.rim_energy`, `lighting.world_strength`, `lighting.exposure`, `lighting.stream_energy`, `lighting.stream_size`
- `stage.card_value`, `stage.card_width`, `stage.ground_value`
- `render.samples`

Bounds come from the scene schema. Samples must be an integer. The full patched spec must pass geometry/animation compatibility checks. Camera transforms, seed, frame, dimensions, scene code, output paths, budgets, and arbitrary expressions cannot change through this mechanism. Camera/geometry/code changes require a deliberate new source version/run outside the bounded parameter-feedback loop.

Example patch fragment, only after a real reviewer approves the change:

```json
"approved_parameter_patch": {
  "liquid.roughness": 0.07,
  "lighting.rim_energy": 1100
}
```

## Budgets and stops

Defaults and hard ceilings:

| Budget | Bound |
| --- | --- |
| Iterations | 3 total, including the first render |
| Views per iteration | Fixed hero, side, top |
| Each renderer subprocess | 180 seconds, including scene setup/export |
| Total active pipeline execution | 1,800 seconds accumulated across runs/resumes |
| Paid service calls | Disabled, $0 |

An iteration can contain three render subprocesses. There are at most nine render launches. Each subprocess receives the smaller of its per-render allowance and remaining total allowance. The process group is killed at timeout, including descendant workers. POSIX (Linux/macOS) is required for process-group termination and file locking. A failed or timed-out render is terminal; there is no hidden retry or paid fallback. A third-iteration `revise` decision records the review and stops `budget_exhausted`, without creating an iteration four.

The total is accumulated active wall-clock execution, including render setup/export and pipeline work; time paused waiting for an external reviewer is excluded. Validation of an incoming review before acquiring an active session is outside this rendering budget. A small amount of process-reaping/persistence overhead can occur after a renderer deadline; no additional renderer is launched with exhausted time. CLI flags can tighten budgets but cannot exceed either the spec's limits or the hard ceilings:

```bash
python -m cgstudio run --spec specs/clear_resin.json --output runs/short \
  --max-iterations 1 --total-seconds 300 --render-seconds 90
```

`paid_usd_spent: 0` describes calls made by this orchestrator. It neither invokes nor accounts for any separately operated reviewer service. Local CPU/GPU power and infrastructure costs are not estimated. To keep the entire workflow paid-API-free, use a human or an already available approved local reviewer.

## Reproducibility and recovery

All three views use the same spec, frame, random seed, dimensions, and renderer configuration. Secondary views skip duplicate native/GLB exports. Each renderer has a separate log and command receipt. Review revision paths cannot change cameras or the seed. Results may still differ across Blender versions, hardware, or renderer builds; the scene manifests report Blender version and settings.

Run folders are never overwritten. File locking prevents concurrent operations on the same run. State writes are atomic. An iteration is reserved before Blender launches, so an interruption cannot silently restore its allowance. Ctrl-C kills the active renderer process group and marks the run interrupted. An abrupt OS kill may leave a `rendering` state; there is intentionally no automatic resume of that ambiguous state. Inspect and stop remaining work, preserve the evidence, and start an explicitly new run if appropriate. Do not edit state to reset limits.

Exit code 0 means an accepted result or a successful stop awaiting review. It does not by itself mean visual acceptance. Exit 2 reports rejected, exhausted, failed, or invalid work; exit 130 reports user interruption. Use `state.json`/`status` for the precise outcome.

## Verification

```bash
python -m unittest discover -s tests -v
```

Tests use an unmistakable test-double renderer that writes tiny fixture PNGs and marked dummy assets; they are not evidence of Blender rendering or visual quality. Coverage includes review pending, three-view evidence binding, stale/tampered reviews, approval rules, strict JSON, allowlisted patches, fixed cameras/seed, iteration ceiling, paid-call prohibition, tightened budgets, nonzero renderer exits, total/per-render deadlines, descendant termination, atomic state flow, and concurrent-run locking. Real Blender/render and viewport verification must be reported separately.
