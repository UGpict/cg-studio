# Project CG Studio

自然言語の制作意図を、再現できるシーン、実レンダー、画像レビュー、修正へつなぐ最小の CG 制作システムです。

## What this is

An executable, local-first resin-pouring **benchmark and review pipeline**. Blender/Cycles is the offline render master. Three.js A and Blender-GLB→Three.js C are separate web comparison routes. No renderer is called high quality just because a script completed.

The first target contains a closed thick glass vessel, closed clear resin volume and meniscus, a continuous procedural stream, a hollow metal feed nozzle, a metal witness cylinder, a physical refraction card, studio lights and three fixed cameras. The card and hovering nozzle are a diagnostic test rig, not a finished commercial composition.

## Current validation status

The first bounded look run ended **rejected / changes requested** after 3 iterations and 9 real views (513.32 active seconds, $0). Those original `samples/` and review records remain unchanged.

A separate [offline visibility prototype](experiments/visibility_v2/README.md) subsequently passed actual three-view readability review. Its 36-frame, 384×384, 12 fps motion demonstration was decoded and all frame pixels were independently inspected. The stream/contact and clear-volume appearance improved. This is prototype acceptance, not a photoreal-final or flicker-free film claim. It uses Cycles-specific optical interfaces and changing Boolean geometry; **equivalent GLB export is not implemented** for this look. The original GLB benchmark remains available separately.

The full software suite passes 103 tests (25 pipeline, 52 compiler, 26 vision protocol). Vision tests use explicitly labeled test doubles; no live vision model is configured. A/C browser pixels and live automatic visual review remain unverified. See the [completion matrix](qa/visibility_v2/completion_matrix.md), [latest comparison](experiments/visibility_v2/matched_denoised_comparison.png) and [three views](experiments/visibility_v2/three_view_final.png).

Scene dimensions are normalized benchmark units, not manufacturing specifications. Remote publication is incomplete; [manual publication](docs/manual-publication.md) records the verified draft-PR state and the authenticated-user import command.

## Quick start

Requirements: Python 3.10+, Blender 4.3+ on PATH. The tested environment uses Blender 4.3.2, CPU rendering, and Python 3.12. No API key, paid renderer, network connection or add-on is required for B. Pillow is optional for numeric pixel summaries.

```sh
python -m cgstudio validate --spec specs/clear_resin.json
chmod +x tests/fake_blender.py  # Restore fixture mode if your ZIP extractor strips it.
python -m unittest discover -s tests -v
python -m cgstudio run --spec specs/clear_resin.json --output runs/my-shot
python -m cgstudio status --output runs/my-shot
```

The pipeline renders `hero.png`, `side.png`, `top.png`, saves `.blend` and `.glb`, and **stops at `review_pending`**. Open all three images, inspect against the brief and role rubrics, and complete a copy of the generated `review.template.json`. Never mark `image_inspected` true without seeing the actual pixels. Then:

```sh
python -m cgstudio resume --output runs/my-shot --review completed_review.json
```

A `revise` review consumes only approved numeric parameter changes and starts the next three-view iteration. An `accepted` review must have no P0/P1 issues. `rejected` stops. Image/spec hashes bind the review to the exact evidence. Camera, budget, executable code and unknown fields cannot be changed through a review.

Defaults and hard ceilings: **3 iterations, 1,800 active seconds total, 180 seconds per render process, $0 paid cost**. Waiting for review does not spend active-render budget. Timeouts stop the renderer process group; a partial/failed render is never accepted. See [QA loop](docs/qa-loop.md).

## Natural language and roles

The closed English/Japanese brief compiler converts supported resin-pour requests into the strict spec and stops on unsupported or contradictory clauses. It is not a general text-to-3D model. Modeling, material/lighting, animation, rendering and visual QA have explicit handoffs in `agents/`. The optional local stdio vision adapter and bounded unattended coordinator are implemented, but no real vision provider is configured and no live autonomous model review has run. The default remains explicit human/agent review. See [brief and vision integration](docs/brief-and-vision.md) for exact supported language, provider requirements, reference-image handling and test-double limits.

Example brief: “Clear resin pours into a thick transparent cup. Show real wall thickness, a clean meniscus, readable refraction, soft contact shadows and a metal object for reflection reference.”

Keep product claims and chemical process requirements separate from the visualization. The original GLB pour uses art-directed fixed-topology animation; the separate offline prototype adds a live Boolean union with changing evaluated topology. Neither is a fluid simulation or chemistry model.

## Compile a supported brief

```sh
python -m cgstudio.brief compile \
  --brief '透明なレジンを厚みのある透明なカップに注ぐ。解像度は512x512。サンプル数は32。' \
  --output runs/brief-report.json --spec-output runs/compiled-spec.json
python -m cgstudio validate --spec runs/compiled-spec.json
```

Unknown clauses block compilation rather than being silently dropped. An unconfigured `python -m cgstudio.auto --output runs/my-shot` does not fabricate a provider result.

## Direct scene build

```sh
blender -b -t 4 -P scripts/build_scene.py -- \
  --spec specs/clear_resin_final.json --out runs/direct \
  --camera hero --frame 18 --render --linear-pass
```

`--linear-pass` saves raw linear EXR/PFM for the optional official OIDN step. Raw and denoised images remain separate. No installed denoiser is assumed and Blender's built-in denoising is off in the tested CPU configuration. See [rendering](docs/rendering.md) for color-pipeline and motion details.

## A / B / C

- A: conventional Three.js procedural scene, pinned npm dependencies, actual WebGL capture harness
- B: Blender Cycles, reproducible CPU renders and fixed-camera visual review
- C: exported Blender GLB imported by the actual Three.js GLTFLoader, with web look handled separately

See [comparison report](docs/comparison-report.md), [web instructions](web/README.md), and machine-readable evidence in `samples/` and `web/results/`.

A/C Chromium rendering was blocked in this execution environment before page load by a socket `EPERM`. A/C are **not visually benchmarked**. Actual GLTFLoader parsing was tested. Successful import does not establish web appearance or GPU performance.

## Layout and provenance

- `specs/`: initial/revised/final parameter specs; baseline retained
- `scripts/`: own scene builder, optional denoise/motion and web capture tools
- `cgstudio/`: strict validation, budget ledger, review gate and CLI
- `agents/`: role instructions; `schemas/`: machine-readable contracts
- `tests/`: deterministic orchestration tests; Blender renders are separately recorded
- `qa/`: actual independent visual reviews, with limitations and unresolved defects
- `samples/`: validated output subset and evidence retained with the deliverable
- `experiments/visibility_v2/`: separately accepted offline prototype, curated evidence and native scene
- `runs/`: reproducible working renders, excluded from Git

The existing film project is untouched. This is a separate local Git repository. Source publication is handled through a draft pull request. No cloud GPU purchase or persistent credential setup is included.
