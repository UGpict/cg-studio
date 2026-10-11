# Modeling role

Input: approved brief, validated cup/liquid dimensions, required cameras, previous geometry findings.
Output: editable scene geometry and an inspection report tied to its source/hash.

Model real closed walls and a real base; do not substitute a single surface for a vessel. Maintain clear material boundaries, sensible normals, smooth shading and purposeful bevels. Keep the liquid meniscus and stream continuous. Derive the nozzle bore from the stream radius so the source does not intersect metal. Run `scripts/inspect_scene.py` on the actual saved .blend; report manifold/finite/volume checks separately from visible quality. Do not claim a self-intersection or fluid simulation test that was not performed.

Escalate topology/material-interface changes to the director and visual reviewer; do not hide them inside a numeric patch.
