# CG Studio role contracts

These are portable role instructions for an assistant or a human running this workflow. They are not a claim that independent model agents or paid APIs run automatically. The Python coordinator executes rendering and enforces the review boundary; a real external reviewer supplies the visual judgment.

| Role | Input | Output | Authority |
| --- | --- | --- | --- |
| Director | User brief, references, restrictions | Validated scene spec and explicit acceptance scope | Sets the brief before the run |
| Scene builder | Immutable iteration spec | Native scene, GLB, three fixed camera renders, manifests | Executes deterministic scene code |
| Visual reviewer | Actual rendered pixels, spec, rubric, optional playback | Hash-bound structured review with priority issues | Accepts/rejects, or approves numeric patch hypotheses |
| Coordinator | Spec, completed reviews, remaining budgets | Next bounded render or explicit terminal/pending state | Applies only allowlisted numeric patches |

Read the individual role files and `docs/qa-loop.md`. No role can expand the fixed budgets, fabricate evidence, or convert measurements into an aesthetic score.

## Specialized production roles

- [Modeling](modeling.md): actual boundaries, normals, thickness and nozzle clearance
- [Material and lighting](material-lighting.md): readable optics and controlled reflection environment
- [Animation](animation.md): source/stream/surface continuity and explicit procedural-motion limits
- [Rendering](rendering.md): frozen source, bounded execution, evidence and denoising provenance

The director and visual reviewer make the final look decision; a completed render never substitutes for that decision.
