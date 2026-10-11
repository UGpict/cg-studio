# Rendering and optional cleanup

The saved scene uses Cycles CPU and AgX. The animated resin fill and shortening continuous stream are fixed-topology shape keys across frames 1–36. This is an art-directed approximation, **not a fluid simulation**. Animated GLB appearance is an approximation of the offline Cycles image.

## Linear passes and color-only OIDN

Add `--linear-pass` to `scripts/build_scene.py` when rendering to preserve a 32-bit scene-linear EXR and RGB PFM beside the original PNG. The official Intel Open Image Denoise binary is optional and is not bundled or automatically downloaded. Set `OIDN_DENOISE` or pass its path explicitly:

```sh
python scripts/denoise.py \
  --input runs/final/hero_linear.pfm --blend runs/final/scene.blend \
  --oidn /path/to/oidnDenoise
```

This runs the official RT filter with `--hdr`, `--device cpu`, `--threads 2`, and `--affinity 0`. It uses **color only**, without albedo or normal auxiliary passes. It does not imply Blender's internal denoiser ran. The tested optional tool is official OIDN 2.5.1 for Linux x86-64.

Raw PNG/PFM/EXR inputs are retained. Outputs have `_color_only_oidn` names; JSON records the exact command, processing time, raw-input hash, and difference metrics. `*_raw_display.png` and the denoised PNG are both converted through the same saved scene's display transform and exposure. Compare these equally processed files, or apply the same cleanup policy to both scene revisions. Never compare a noisy baseline with a cleaned revision as evidence of material improvement.

PFM stores scene-linear RGB values bottom-to-top. `pfm_to_png.py` loads those float pixels into a linear Blender image and calls `save_render` with the saved scene's AgX settings. It does not apply sRGB before AgX, clamp HDR input, or flip pixels a second time. Use the matching `.blend` file: another scene may have different exposure or view settings. The current conversion is for opaque RGB studio renders; transparent-background RGBA preservation is not implemented.

Denoising can soften reflections, thin glass and resin details. It does not repair geometry, optics, an inappropriate render setup, or prove noise-free ground truth. Evaluate matched raw/cleaned crops. Filtering is spatial, not temporal; sequential frames may flicker.

## Budgeted motion preview

```sh
python scripts/render_motion.py \
  --blend runs/final/scene.blend --out runs/motion \
  --width 384 --height 384 --samples 16 --frames 36 --fps 12 \
  --budget-seconds 400 --frame-timeout 180
```

One Blender process renders the saved animation into a fresh output folder. Defaults produce 36 raw PNGs and a three-second, 12 fps, H.264 MP4. Add `--oidn /path/to/oidnDenoise` for per-frame color-only cleanup, retaining raw PNGs, EXR/PFM passes, equally display-processed raw comparisons, and cleaned PNGs. No packages are installed, paid services called, or source scene files altered.

The total watchdog includes rendering, optional cleanup, encoding and validation; per-frame watchdog bounds a stuck render. The Blender worker runs in an owned POSIX process group, and deadline cleanup kills the complete group, including in-flight denoiser children. A timeout or error preserves partial raw frames and writes a failed validation report. Existing frame folders are rejected to prevent stale output being mistaken for a completed render. Preview quality and time depend on CPU availability; exceeding the budget is a reported failure, not a success claim.

`validation.json` records actual PNG decode count, actual ffprobe decoded MP4 frame count and duration, full-video decode success, dimensions, render timings, and first/last image differences. `contact_sheet.png` shows first, middle and last images for visual inspection. Decode success only establishes a readable video; the contact sheet and playback still need review for animation, continuity, reflections, clipping and flicker. A nonzero first/last difference is not evidence of a correct fluid simulation.

## Verified sample from this workspace

- `runs/final/hero_linear_color_only_oidn.png`: official OIDN 2.5.1 color-only output, with original PFM hash unchanged. The re-displayed raw PFM matches the original 640×640 PNG within a mean 0.454 and maximum 2 of 255 channel levels, consistent with quantization/dithering differences. This check rules out a large display-transform or orientation mismatch; it does not establish perfect pixel equality.
- `runs/motion_final/preview.mp4`: completed in 350.85 seconds; 384×384, 16 samples, 36 decoded H.264 frames at 12 fps, exactly 3.000 seconds. Full video decode and all 36 selected PNG decodes passed. Raw, matched raw-display and color-only OIDN frames are retained.
- `runs/motion_final/geometry_check.json`: evaluated liquid top heights at frames 1/18/36 are 0.652/0.992/1.352. Stream bottom remains approximately 0.0294 below the nearest sampled surface vertex. Counts stay fixed at 2,818 liquid and 2,328 stream vertices. This is approximate mesh-contact evidence, not a fluid solve.
- Early/middle/late contact-sheet inspection shows the rising fill. The upper stream is still a hard-to-read hairline and can look interrupted; the low-sample transparent surfaces are soft. No flicker-free or beauty-quality approval is claimed. This is a QA preview, not an accepted final render.
- Timeout-path integration testing with a fake renderer and child process confirms whole-process-group termination and a failed validation report. The successful preview predates that watchdog-only implementation change; it did not hit its deadline.
