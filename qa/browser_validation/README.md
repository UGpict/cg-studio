# Frozen MVP browser validation and parity audit

Date: 2026-10-11. Scope: `specs/clear_resin_final.json` and `samples/resin_scene.glb`; the separate `visibility_v2` experiment is excluded.

## Result

**A/C WebGL pixels, appearance, renderer provenance and frame timings remain NOT RUN.** The existing Node GLTFLoader import test is a static import result, not a visual pass. No image or performance result was fabricated or substituted with Cycles output.

Ordinary browser navigation to the localhost-only web harness failed with `net::ERR_CONNECTION_REFUSED`. An independent process request was also refused while the server session was active. A bounded same-process server/request test returned HTTP 200 and the expected harness title. The tested loopback endpoint was therefore not reachable by the browser in this environment. No WebGL image or frame timing was obtained. The earlier direct Chromium launch also failed before page load with socket `EPERM`. The test server was stopped.

## Hero-pose comparison defect discovered and fixed

The original frozen C viewer imported the GLB without sampling its animation. This defect is now fixed in `web/viewer.js`. Both morph meshes default to weights `[1, 0]`, the fill-start pose. This is not the requested hero pose:

| Static evaluated vertex evidence | C at load | C after sampling hero | A's hero formula |
|---|---:|---:|---:|
| Liquid upper bound Z | 0.652000010 | 0.992000015 | 0.96 + 0.032 = 0.992 |
| Stream lower bound Z | 0.595000029 | 0.935000005 | 0.96 - 0.025 = 0.935 |

Both exported clips use absolute timestamps from frame 1 / 12 fps to frame 36 / 12 fps. Play both clips with one `THREE.AnimationMixer(loaded.scene)` and sample **18 / 12 = 1.5 seconds**, rather than `(18 - 1) / 12`. The tested weights at that time are approximately `[0.514285684, 0.485714287]`.

The authorized correction is now in `web/viewer.js`. It plays both clips once, clamps the final pose, samples absolute frame/fps time, and logs frame, fps, time, clip names and resulting morph weights. `test_hero_pose.mjs` extracts and executes the actual viewer sampling block with the real GLTFLoader. It verifies the hero bounds, both mesh weights, unchanged imported material JSON, all three imported camera transforms, and frame-36 endpoint clamping. These assertions passed. The viewer has still not executed in a browser, so visual parity remains unverified.

## Confirmed source-level properties

- A constructs actual procedural Three.js geometry. C uses the real `GLTFLoader` and preserves imported materials. Neither route uses a Cycles PNG as its rendered result.
- Both modes construct their camera from the same spec, use Z-up, 640×640, 4.7 orthographic extent, matching hero/side/top positions and targets, and the same web light/environment setup.
- Imported GLB camera positions and extent also agree with those inputs to floating-point tolerance. Imported cameras are not used by the viewer. The web camera uses near/far 0.01/200; the exported camera is approximately 0.1/1000.
- Cup: transmission 1, IOR approximately 1.46, thickness approximately 0.065, roughness approximately 0.025.
- Bulk resin: transmission 1, IOR approximately 1.49, thickness approximately 1.6; stream: separate thickness approximately 0.18. Resin attenuation color approximately [0.94, 0.99, 1], attenuation distance approximately 16.6667. These are web optical approximations.
- Glass/resin use FrontSide in both. Imported opaque GLB materials use DoubleSide, while A's procedural materials default to FrontSide. A uses MeshPhysicalMaterial for all materials; C opaque imports are MeshStandardMaterial. These are not a silent material replacement, but they are differences to disclose and investigate if pixels differ.
- A's witness cylinder and cards are un-beveled; C contains Blender's bevel/modifier output. Lathe poles, triangulation, ring phase and normals also differ. Source-level alignment is not geometric identity.

## Remaining A/B/C limitations

A and C share their web lighting, but B does not have an identical reflection/light transport environment. Web uses a PMREM RoomEnvironment, rectangle-light energy conversion and an extra directional-light shadow approximation; Cycles uses its scene world and area lights. Web also sets an unscaled background color separately from environment intensity, whereas Cycles world radiance is scaled by world strength. Three AgX and Blender AgX are not established colorimetric equivalents. Web transmission does not reproduce path-traced caustics or Blender volumetric scattering. Frame matching alone cannot establish optical parity.

The capture harness explicitly requests SwiftShader. Any successful run with that harness is a software-rasterizer smoke benchmark, not target-device GPU performance. It reports the observed WebGL renderer string; do not infer it before a successful render. Timings include `renderer.render()` plus `gl.finish()` wall-clock cost, not GPU timer queries.

## Reproduce and continue safely

Static audit, runnable in the current checkout:

```sh
cd /path/to/cg_studio
node qa/browser_validation/audit_import.mjs > qa/browser_validation/import_audit.json
node qa/browser_validation/test_hero_pose.mjs > qa/browser_validation/pose_test_result.json
```

For actual A/C images, use an authorized environment with Node/npm, an installed official Chromium executable, permitted local sockets, and a browser that can reach the same loopback HTTP server. No public hosting is required. Use the corrected viewer and retain its source hash. Then:

```sh
cd /path/to/cg_studio/web
npm ci --ignore-scripts --cache /tmp/cg-npm-cache
node ../scripts/capture_web.mjs --chromium=/absolute/path/to/chromium --modes=A,C --cameras=hero,side,top --width=640 --height=640 --frames=30 --out=web/results_verified
```

Inspect all six actual canvas PNGs and `web/results_verified/benchmark.json`. Confirm `status`, renderer provenance, pose, material values, dimensions, console errors and timing limitations. Compare to the frozen B images, keeping lighting/material differences explicit. A completed import or browser startup alone is not acceptance.

## Evidence

- `browser_attempt.json`: exact observed access failures, successful same-process HTTP check, pre-correction source hashes, and unrun A/C stages.
- `pose_test_result.json`: passing geometry/material/camera assertions and corrected viewer/spec/GLB source hashes.
- `test_hero_pose.mjs`: repeatable regression test that executes the actual viewer animation-sampling block without creating a browser or WebGL context.
- `import_audit.json`: source hashes, default and corrected evaluated vertex bounds, imported material values, cameras and animation tracks.
- `audit_import.mjs`: reproducible static importer audit; creates no browser and makes no network requests.
