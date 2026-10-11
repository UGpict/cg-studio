# Project CG Studio

自然言語の制作意図を、再現できるシーン、実レンダー、画像レビュー、修正へつなぐ最小の CG 制作システムです。

## What this is

An executable, local-first resin-pouring **benchmark and review pipeline**. Blender/Cycles is the offline render master. Three.js A and Blender-GLB→Three.js C are separate web comparison routes. No renderer is called high quality just because a script completed.

The first target contains a closed thick glass vessel, closed clear resin volume and meniscus, a continuous procedural stream, a hollow metal feed nozzle, a metal witness cylinder, a physical refraction card, studio lights and three fixed cameras. The card and hovering nozzle are a diagnostic test rig, not a finished commercial composition.

## Current validation status

The pipeline is executable and tested. The first bounded look run ended **rejected / changes requested** after 3 iterations and 9 real views (513.32 active seconds, $0). The final hero still loses part of the clear stream against the dark background. This repository includes working outputs and the failed quality gate; it does not claim that the final-film quality goal is achieved.

See `samples/three_view_final_attempt.png`, `samples/matched_denoised_comparison.png` and `qa/final_visual_review.json`. The MP4 is explicitly the earlier iteration-002 look, with rising fill and an unfinished optical treatment. Scene dimensions are normalized benchmark units, not manufacturing specifications.

## Quick start

Requirements: Python 3.10+, Blender 4.3+ on PATH. The tested environment uses Blender 4.3.2, CPU rendering, and Python 3.12. No API key, paid renderer, network connection or add-on is required for B. Pillow is optional for numeric pixel summaries.

```sh
python -m cgstudio validate --spec specs/clear_resin.json
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

The director interprets a brief and fills the strict JSON scene spec; it does not execute arbitrary text as Python. Modeling, material/lighting, animation, rendering and visual QA have explicit handoffs in `agents/`. This repository runs without an LLM service. An unattended vision/API adapter is **unconfigured**: human or an image-capable agent review is required. No fabricated vision score or automatic approval is provided.

Example brief: “Clear resin pours into a thick transparent cup. Show real wall thickness, a clean meniscus, readable refraction, soft contact shadows and a metal object for reflection reference.”

Keep product claims and chemical process requirements separate from the visualization. The pour is an **art-directed fixed-topology animation, not a fluid simulation or chemistry model**.

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
- `runs/`: reproducible working renders, excluded from Git

The existing film project is untouched. This is a separate local Git repository. No GitHub repository, remote push, cloud GPU purchase or persistent access has been created.
