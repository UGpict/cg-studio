# Visibility v2: bounded look-development experiment

This folder is independent of the frozen MVP. Core code and prior gate evidence are unchanged.

## Scope and budget

- At most 3 candidates, each at the original hero/side/top cameras, frame 18, 640×640, seed 42 and AgX display transform.
- At most 1,200 active local execution seconds; at most 180 seconds per render; no paid APIs or additional software.
- Static review first. Motion is permitted only after the director accepts the three-angle still look, under a separately documented remaining budget.
- The reviewer and director retain the original visual bar. No user-supplied photographic references were provided. Independent QA later inspected two public manufacturer photos for qualitative stream/contact cues; no exact image-reference match is claimed. See `../../qa/visibility_v2/reference_evidence.json`.

## Candidate 001 hypothesis

The baseline resin is separated from the glass by a thin air shell. This supplies two unnecessary high-contrast refractive interfaces and makes the receiving volume look like a separate bulb. The candidate fits the liquid wall to the actual tapered inner glass profile with a small overlap instead. This is an optical modeling approximation; it does not by itself prove correct nested dielectric transport.

Narrow reflection strips are now truly vertical, spanning the entire free stream, rather than finite tilted sources that disappear from its reflected field at some heights. A metal feed tube continues upward outside the frame to give the nozzle a support/source. The standalone diagnostic refraction card is removed and the ground/world are raised slightly. Clear resin transmission, IOR and zero cloudiness are preserved.

All source and spec snapshots, raw and separately OIDN-filtered images, local timings and image identities are saved per candidate. This is a multi-variable look-development revision, not a controlled renderer benchmark. OIDN is single-frame, HDR, color-only; no temporal stability is implied.

## Candidate 002: explicit optical boundaries

The slight-overlap-only candidate improved neither the dark internal band nor the bulb reading enough. Candidate 002 keeps the candidate-001 lighting, cameras, sample count and general composition, but explicitly assigns three kinds of surface boundary:

1. Air/glass exterior and dry glass interior use the original glass IOR 1.46.
2. Submerged interior glass faces, oriented from glass into the liquid cavity, use relative IOR glass/resin = 1.46/1.49 = 0.9798658.
3. The liquid's free surface and stream retain IOR 1.49. Its side/bottom boundary carries absorption without another surface refraction, avoiding a second artificial air interface.

The cup has a moving wet-line topology ring and matching shape keys so the material partition follows the animated fill. Its outer silhouette remains unchanged. This is a Cycles-specific explicit interface model, not proof of exact resin properties or general-purpose nested dielectric support. The model has no cloudiness and does not use an opaque white fluid.

## Candidate 003: final bounded still-look candidate

The final candidate adds support rings along the existing straight tapered wall geometry, limiting smooth-normal interpolation from rim/base bevels. A live exact Boolean union removes the stream's hidden end-cap and duplicated receiving-surface intersection. The input meshes still use shape keys, but evaluated union topology can change. Preflight verifies a single connected, manifold, positive-volume cup and resin at frames 1, 18 and 36. This is geometry evidence, not a motion-quality pass.

Equivalent GLB export is intentionally not attempted for this experimental boundary/Boolean treatment. The original pipeline's GLB route is preserved unchanged. The candidate-003 native Blender scene remains suitable for separate bounded Cycles animation testing after still acceptance.


## Executed result

Independent three-view pixel review accepted candidate 003 for the still-look prototype. The director separately inspected and approved the hero direction. This is not photoreal-final, complete-film or GLB/web parity acceptance. See `../../qa/visibility_v2/review_003.json` for image-bound review evidence and remaining P2 presentation limits.

The experiment rendered exactly three candidates × three fixed views. Each raw image is retained beside a separate HDR color-only OIDN result. `evidence_checks.json` verifies unchanged cameras/frame/dimensions/seed and source/image hashes across all candidates. All 36 evaluated native-scene geometry states are manifold, single-component and positive-volume, with monotonically increasing resin volume; this does not establish temporal visual quality.

The authorized short final-look motion preview is a separate low-sample 384×384, 36-frame, 12 fps test from the candidate-003 native scene. It may start only after independent still approval. Its runner shares the original 1,200-second experiment allowance and reserves an additional conservative 60 seconds for auxiliary checks. Accounted execution seconds are wall-clock execution on CPU, not CPU-core-seconds or power consumption.


## Motion result and reproducibility checkpoint

The final-look preview completed: 36 H.264 frames, 384×384, 12 fps, 3 seconds. All PNGs and the MP4 decode successfully. Independent QA inspected all 36 rendered frames, finding rising fill, legible source/stream/contact and no obvious large union or silhouette pop. This is a validated low-sample motion demonstration; live playback, subtle temporal flicker and film-quality approval remain unclaimed. See `../../qa/visibility_v2/motion_review_003.json`.

Measured render/denoise/motion execution was 902.91 seconds. Including a conservative 60-second auxiliary allowance gives 962.91 of the 1,200-second bound. Exactly 3 candidates and 9 fixed-view renders were used; paid API cost was $0.

The checkpoint contains the native scene, exact final builder/spec, raw and OIDN stills, baseline comparison, final motion/validation and independent QA. It excludes cached manufacturer photos. Open `iteration_003/scene.blend` in Blender, or reproduce a still from the extracted package root with:

    blender -b -t 4 -P experiments/visibility_v2/build_scene.py -- --spec experiments/visibility_v2/spec_003.json --out runs/new_reproduction --camera hero --frame 18 --render --linear-pass

The included motion script and its local helper modules support a separate bounded preview with Blender, Python/Pillow and ffmpeg already installed. OIDN is optional and must already be installed; no software is downloaded automatically. Avoid reusing an existing output folder.

## Curated repository package

Only the final prototype source/native scene, final three-view evidence, short motion, numerical audit records and independent review are committed here. Large intermediate renders, raw linear EXR/PFM caches, historical machine-specific runner scripts and downloaded reference photographs are excluded. The budget/evidence records preserve the executed three-candidate history; rerendering is a new run and must use a new output path and explicit limits.

The committed current builder corrects a metadata-only inherited fixed-topology description. The exact source used for the reviewed renders remains `iteration_003/builder_snapshot.py`; its hash is preserved in the manifests. Geometry, materials and animation were not changed by that wording correction. To reproduce the exact rendered source, use that snapshot in place of `build_scene.py` in the command above.

A portable bounded motion reproduction command is:

    python experiments/visibility_v2/render_motion.py --blend experiments/visibility_v2/iteration_003/scene.blend --out runs/prototype-motion --width 384 --height 384 --samples 16 --frames 36 --fps 12 --budget-seconds 400

Add `--oidn /your/installed/oidnDenoise` only if the official binary is already installed. Without it the preview remains raw; the saved demonstration used separately labeled color-only OIDN. This command never installs software or calls a paid endpoint.
