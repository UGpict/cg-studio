# CG Studio independent QA criteria

Status: review plan, not an executed visual or runtime pass.

## Evidence discipline

- Inspect actual rendered pixels, not just source parameters or renderer logs.
- Compare baseline and improved at the same three named cameras, frame, crop, resolution, and display transform. Record changes in light, material, geometry, samples, and render time. If camera/light differences prevent attribution, label the comparison as a look-development revision rather than a controlled benchmark.
- A six-image set is evidence for one still-state at three angles. It is not evidence for temporal continuity, full-film rendering, or renderer parity.
- No user visual reference was included in the review handoff. Judge optical and geometric plausibility, and do not claim reference-image agreement. A technical source is not a photographic match target.
- Report each finding with priority, owner, image/view evidence, a concrete correction, and a testable acceptance check. Do not fabricate similarity scores or vision metrics.

## Visual checks

### Modeling

1. Cup outer wall, inner wall, rim, and base form a plausible finite-thickness vessel. Review silhouette, rim cross-section, elliptical perspective, normals, and visible discontinuities in all three views.
2. Liquid reads as a filled volume bounded by the inner vessel, with a deliberate free surface and meniscus. It must not resemble an empty cup, an opaque insert, a floating disk, or a liquid extending through the wall.
3. Stream has plausible attachment and continuity at its source and destination. Inspect for detached/hovering tips, sharp tangency changes, repeated bead shapes, and obvious tube intersections. A procedural curve can be artistically acceptable but must not be called a fluid simulation.
4. If bubbles are present, their placement/scale must support the liquid rather than resemble painted dots or floating geometry outside the vessel.

### Material and lighting

1. Cup and liquid both remain legible through edge reflections, refraction, absorption, or controlled background contrast. Clear must not mean invisible.
2. Transmission must be differentiated from alpha transparency; opaque materials should remain opaque, and metal should carry plausible environment reflections without diffuse plastic appearance.
3. Highlights have intentional shape and preserve edge detail. Reject broad clipped white wash, excessive bloom, milky unintended scattering, or uniformly black glass.
4. Objects contact their support with believable shadow/occlusion. Distinguish a production choice to suppress caustics from proven physically complete light transport.

### Animation

1. Inspect neighboring frames or actual video before claiming continuity. A still-frame mesh intersection is not a temporal test.
2. Check stream motion, fill-level direction, impact position, no penetration/pop/disappearance, and stable silhouettes.
3. Check flicker from low sample counts/denoising, exposure drift, and motion-blur consistency. Confirm loop behavior only if looping is requested.

### Rendering

1. Actual renderer, software version, backend/device, samples, resolution, frame, timing, and output path must be recorded.
2. Verify all expected images are present, decodable, nonempty, and correspond to their labels.
3. Inspect meaningful full-size details. Contact sheets support navigation; they do not replace source-image inspection.
4. Do not infer GPU use from a library name, a configured backend, or a browser capability string. Report the actual device result.

## Software and claims checks

- Distinguish executed/passed, executed/failed, blocked, and not run.
- Inspect orchestrator stopping conditions: bounded review iterations, stop after acceptance or budget exhaustion, and an explicit terminal state for missing review credentials or adapters.
- No API key or model adapter means `pending_review`/`review_unavailable`, not an autonomous visual pass. A deterministic heuristic may be useful but must be named as such.
- Verify approved feedback can be traced to actual parameter/file changes and a new render. Store input/output artifact identities and decisions.
- The A Three.js, B Cycles, and C GLB-to-web routes require their own actual runtime evidence. A GLB export is not proof of browser playback, and a browser load is not proof of Cycles appearance parity.
- No untrusted external code installation or heavy concurrent render is part of this review.

## Decision vocabulary

- Accepted for still-look prototype: reviewed three-view still-state meets the agreed visual bar; temporal/full-film work remains unproven.
- Changes requested: a named visible or software defect blocks the agreed deliverable.
- Pending evidence: required artifacts or runtime stages are not yet available.
- Final quality acceptance belongs to the project director.
