# A/B/C benchmark status

Measured in the current environment on 2026-10-11. This is an implementation and bounded validation report, not a performance ranking across working renderers.

## A — conventional Three.js

Implemented and syntax/module checks passed. The procedural scene follows the shared dimensions and cameras. Three.js 0.180.0 and playwright-core 1.55.1 are pinned. Chromium failed before page load with `process_singleton_posix: socket() failed: Operation not permitted`; the reviewed elevated attempt failed the same way. Therefore no A image, frame time or GPU result exists. Exact error: `web/results/benchmark.json`.

## B — Blender Cycles

Actual Blender 4.3.2 CPU images were rendered and independently inspected. First 640×640 hero at 32 samples took about 16.0 seconds of render time. A 128-sample revision took about 70.8 seconds. A contrast-focused 96-sample revision took about 54.1 seconds. These are whole-render wall times in a shared CPU environment, not normalized hardware scores. Do not infer a frame-rate or predict a full film without a representative motion test.

Initial problems: heavy grain, a pale lower-liquid reflection that could read as opaque resin, and poor stream contrast above the rim. Evidence-based changes lowered glass/resin roughness, darkened the diagnostic card and floor, added a controlled stream reflection strip and increased stream diameter. Fixed cameras and initial outputs are retained. Changes improve edges and reflections; unresolved visual limitations are recorded in `qa/`. Optional OIDN output is labeled separately from raw Cycles output. Do not credit denoising as a geometry improvement.

## C — Blender GLB → Three.js

Actual GLTFLoader parsed the exported GLB without a WebGL renderer. It retained KHR_materials_transmission, KHR_materials_ior and KHR_materials_volume. After correcting export hints, the cup imports with thickness about 0.065 and IOR 1.46; the bulk resin thickness is 1.6 and IOR 1.49; the stream has a separate approximate web thickness of 0.18. `web/results/glb_validation.json` records the actual values.

These thickness values are rasterized web approximations; Cycles uses closed geometry. Volumetric scattering, Cycles lighting and appearance do not transfer. Fixed-topology morph animation is exported, not a liquid simulation cache. Chromium was blocked for C exactly as for A, so visual fidelity and performance remain **not run**.

## What the evidence supports

- B is executable in this CPU environment and produces real before/after pixels and source assets.
- The review gate and bounded rerender path are tested separately from renderer image quality.
- C has a working asset import path; A/C are ready for a permitted browser environment, pending actual image review.
- No claim of A/B/C visual parity, real-time photorealistic liquid, GPU acceleration or fully autonomous vision approval is supported.

## Next bounded experiments

1. Resolve the remaining clear-resin readability/stream contrast issues in actual pixels before expanding scene complexity.
2. Review a short native motion sequence for flow continuity and temporal noise.
3. Run A and C on an authorized working browser, then compare matched views and report material/lighting differences rather than silently replacing the look.
4. Add the cloudy → clear material transition after the clear-pour look is accepted. The transition is a user-directed process visualization, not a universal chemical readiness claim.

## Final bounded outcome

The real coordinator consumed two independent revise reviews and the third rejected review. Exactly 3 iterations / 9 views completed in 513.32 active seconds at zero paid cost. No fourth render ran. The final dark/narrow-card experiment reduced the pale lower-fill wash, but hero stream contrast still fails. All three raw and separately labeled OIDN outputs were inspected. `qa/terminal_state.json` and `qa/final_visual_review.json` contain the actual terminal decision.

Actual scene checks found and corrected loose zero-face pole edges. The final cup, liquid and stream have zero non-manifold edges, positive signed volume and finite coordinates. The nozzle bore is derived from stream radius; recorded clearance is 0.006 scene units. These checks do not establish fluid physics, optical accuracy or freedom from every self-intersection.

The earlier-look motion preview completed in 350.85 seconds: 36 decoded frames, 384×384, 12 fps, 3.0 seconds. It uses color-only spatial OIDN and is not a final temporal-quality pass. Its visible rising fill and sampled geometric contact are supported; a fluid simulation and flicker-free film are not claimed.

Remaining work: controlled stream-background separation without darkening the vessel; a physically readable liquid free surface; multiview acceptance; short-motion optical consistency; actual A/C WebGL visual comparison; then the user-requested cloudy-to-clear transition.
