# Rendering role

Input: frozen source/spec, cameras, seed, sample count, hard time/cost limits.
Output: actual pixels, per-camera manifests/logs, source assets and measured runtime.

Freeze source during a multiview iteration. Capture source/spec SHA-256 and renderer/device/version. Use a process group and terminate descendants on timeout. Do not start another attempt after the limit. Keep all raw frames and label optional denoised frames; compare identical display transforms and apply the same treatment to before/after. OIDN color-only is not an albedo/normal or temporal denoise pass.

Software Chromium is not hardware GPU evidence. A/C require actual WebGL-rendered pixels; record not-run on environment failure. Never substitute a Cycles/Workbench frame as a Three.js baseline.
