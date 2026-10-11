# CG Studio A/C browser comparison

Implemented with pinned Three.js 0.180.0 and playwright-core 1.55.1 from npm.

- **A:** Conventional procedural Three.js scene, using the same parameter spec, 128-segment thick cup, fill volume and meniscus, 96×24 stream, nozzle and metal witness. Witness cylinder and card bevels differ from Blender; those differences are logged.
- **C:** Real Blender-exported GLB loaded through GLTFLoader, without silently replacing imported materials. Y-up GLB root is rotated back to Blender Z-up.
- Cameras match `specs/clear_resin_final.json`: orthographic hero, side and top, 640×640 by default.
- Both web modes use exactly the same environment/light setup. Cycles vs web lighting is not identical: PMREM reflections, area-light energy mapping and a directional shadow approximation are explicitly documented in the runtime report.
- WebGL transmission is a rasterized approximation. No path-traced caustics or fluid-simulation claim is made.

## Run

From this directory:

    npm ci --ignore-scripts --cache /tmp/cg-npm-cache
    node ../scripts/capture_web.mjs --modes=A,C --cameras=hero,side,top --frames=8

The capture script starts its own localhost-only file server, launches installed Chromium, renders the actual canvas and writes PNG screenshots and `results/benchmark.json`. It defaults to software SwiftShader for reproducibility in headless cloud environments; it reports the actual WebGL renderer string when initialization succeeds. It cannot establish target-device performance.

For interactive use, serve the project root with a static HTTP server and open `/web/index.html?mode=A` or `?mode=C`. This does not publish the project.

Options: `--out=web/results`, `--spec=../specs/clear_resin_final.json`, `--glb=../samples/resin_scene.glb`, `--width=640`, `--height=640`, `--frames=8`, `--chromium=/usr/bin/chromium`.

For GLB material/geometry import validation without WebGL:

    node validate_glb.mjs ../samples/resin_scene.glb

## Actual validation result (2026-10-11)

JavaScript syntax checks and Three.js/GLTFLoader module imports passed. The real `samples/resin_scene.glb` parsed successfully through GLTFLoader, with transmission, IOR and volume extensions retained; see `results/glb_validation.json`.

Both normal and reviewed escalated Chromium launches failed before loading any page with `process_singleton_posix: socket() failed: Operation not permitted`. Thus A/C screenshots and frame timing measurements are **not run**, not passed. No renderer string or hardware GPU evidence was observed. Raw failure text and each unrun camera are in `results/benchmark.json`.

The initial cup thickness omission was corrected. Final GLTFLoader evidence records cup thickness 0.065, bulk-resin thickness 1.6, and separate stream thickness 0.18. These are web approximations. A GLTFLoader parse pass is not a WebGL visual pass.

## Measurement limitations

When runnable, timings include `renderer.render()` and `gl.finish()` wall time after three warmup frames. This measures CPU/driver/GPU completion, not a GPU timer query. Compilation/first-frame time is separate. The actual software renderer is labeled. Small sample counts are smoke benchmarks only. PNGs are actual canvas captures; they are never substituted with Blender output.
