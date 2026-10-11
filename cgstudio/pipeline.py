"""Local render → explicit visual-review gate → bounded revision orchestration."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import os
from pathlib import Path
import time
import uuid

from .budget import BudgetExceeded, Limits, run_renderer
from .io import PipelineError, read_json, sha256_file, write_json
from .metrics import image_measurements
from .review import CAMERAS, apply_patch, review_template, validate_review
from .spec import validate_spec

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ("scene.blend", "scene.glb", "scene_manifest.json") + tuple(f"{camera}.png" for camera in CAMERAS) + tuple(f"manifest_{camera}.json" for camera in CAMERAS)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def run_lock(output: Path):
    if os.name != "posix":
        raise PipelineError("This pipeline requires POSIX process and file locking")
    import fcntl
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".pipeline.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineError("This run is already active in another process") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class ActiveSession:
    """Accumulate execution time; time waiting for a person to review is excluded."""
    def __init__(self, output, state):
        self.output = output
        self.state = state
        self.base = state["active_seconds"]
        self.started = time.monotonic()

    def used(self):
        return self.base + time.monotonic() - self.started

    def save(self):
        self.state["active_seconds"] = round(self.used(), 6)
        self.state["updated_at"] = utc_now()
        write_json(self.output / "state.json", self.state)


def renderer_command(blender: str, spec: Path, target: Path, frame: int, camera="hero", builder_path=None):
    command = [blender, "-b", "-t", "4", "-P", str(builder_path or ROOT / "scripts" / "build_scene.py"),
            "--", "--spec", str(spec), "--out", str(target), "--camera", camera,
            "--frame", str(frame), "--render", "--linear-pass"]
    if camera != "hero":
        command.append("--no-export")
    return command


def _render_iteration(session: ActiveSession, spec: dict, blender: str):
    state = session.state
    limits = Limits(**state["limits"])
    if len(state["iterations"]) >= limits.max_iterations:
        state["status"] = "budget_exhausted"
        state["stop_reason"] = "Maximum render iterations reached; no additional render was started"
        session.save()
        return state
    try:
        limits.render_timeout(session.used())
    except BudgetExceeded as exc:
        state["status"] = "budget_exhausted"
        state["stop_reason"] = str(exc)
        session.save()
        return state
    number = len(state["iterations"]) + 1
    relative = f"iteration_{number:03d}"
    target = session.output / relative
    target.mkdir()  # Existing output never gets silently overwritten.
    spec_path = target / "spec.json"
    write_json(spec_path, spec)
    builder_path = target / "builder.snapshot.py"
    builder_path.write_bytes((ROOT / "scripts" / "build_scene.py").read_bytes())
    builder_hash = sha256_file(builder_path)
    entry = {"iteration": number, "directory": relative, "status": "rendering",
             "started_at": utc_now(), "spec_sha256": sha256_file(spec_path), "builder_sha256": builder_hash,
             "renders": [], "multiview_validated": False}
    state["iterations"].append(entry)  # Reserve the attempt before launching Blender.
    state["status"] = "rendering"
    session.save()
    try:
        for camera in CAMERAS:
            timeout = limits.render_timeout(session.used())
            if sha256_file(builder_path) != builder_hash:
                raise PipelineError("Frozen scene builder changed during the iteration")
            command = renderer_command(blender, spec_path, target, state["frame"], camera, builder_path)
            render = {"camera": camera, "command": command, "timeout_seconds": timeout}
            entry["renders"].append(render)
            session.save()
            receipt = run_renderer(command, target / f"render_{camera}.log", timeout)
            render.update(receipt)
            session.save()
            if receipt["returncode"] != 0:
                raise PipelineError(f"{camera} renderer exited with code {receipt['returncode']}; see {relative}/render_{camera}.log")
        for name in ARTIFACTS:
            path = target / name
            if not path.is_file() or path.stat().st_size == 0:
                raise PipelineError(f"Missing or empty renderer artifact: {relative}/{name}")
        manifest = read_json(target / "scene_manifest.json")
        if not isinstance(manifest, dict):
            raise PipelineError("scene_manifest.json must contain an object")
        with (target / "scene.glb").open("rb") as glb:
            if glb.read(4) != b"glTF":
                raise PipelineError("scene.glb is not a binary glTF artifact")
        measures = {camera: image_measurements(target / f"{camera}.png") for camera in CAMERAS}
        for camera, measure in measures.items():
            if (measure["width"], measure["height"]) != (spec["render"]["width"], spec["render"]["height"]):
                raise PipelineError(f"{camera} render dimensions do not match the spec")
        write_json(target / "image_measurements.json", measures)
        entry["artifact_sha256"] = {name: sha256_file(target / name) for name in ARTIFACTS}
        entry["images_sha256"] = {camera: measures[camera]["image_sha256"] for camera in CAMERAS}
        entry["image_sha256"] = entry["images_sha256"]["hero"]
        entry["multiview_rendered"] = True
        entry["status"] = state["status"] = "review_pending"
        entry["finished_at"] = utc_now()
        template = review_template(state["run_id"], entry)
        write_json(target / "review.template.json", template)
        write_json(target / "review_request.json", {
            "run_id": state["run_id"], "iteration": number,
            "images": {camera: f"{camera}.png" for camera in CAMERAS},
            "image_sha256": entry["image_sha256"], "images_sha256": entry["images_sha256"],
            "spec": "spec.json", "spec_sha256": entry["spec_sha256"],
            "review_template": "review.template.json", "review_schema": "schemas/review.schema.json",
            "instructions": "Inspect the actual hero.png, side.png, and top.png pixels against the spec and QA rubric. Fill the template as a human or vision-model reviewer. Measures are not a visual verdict. Do not attest image_inspected unless all three images were inspected.",
            "qa_rubric": "qa/acceptance_criteria.md",
        })
    except BudgetExceeded as exc:
        entry["status"] = state["status"] = "budget_exhausted"
        entry["error"] = state["stop_reason"] = str(exc)
    except KeyboardInterrupt:
        entry["status"] = state["status"] = "interrupted"
        entry["error"] = "Interrupted; renderer process group terminated"
        raise
    except Exception as exc:
        entry["status"] = state["status"] = "failed"
        entry["error"] = str(exc)
    finally:
        session.save()
    return state


def start_run(spec_path: Path, output: Path, blender="blender", limits=None, frame=None):
    spec_path, output = spec_path.resolve(), output.resolve()
    spec = read_json(spec_path)
    validate_spec(spec)
    declared = spec["budget"]
    spec_limits = Limits(declared["max_iterations"], declared["total_seconds"], declared["per_render_seconds"], declared["max_paid_cost_usd"])
    if limits:
        if (limits.max_iterations > spec_limits.max_iterations or limits.total_seconds > spec_limits.total_seconds or limits.render_seconds > spec_limits.render_seconds):
            raise PipelineError("Command-line limits may tighten, but not exceed, the spec budget")
    else:
        limits = spec_limits
    frame = spec["animation"]["hero_frame"] if frame is None else frame
    if type(frame) is not int or not 1 <= frame <= spec["animation"]["frames"]:
        raise PipelineError("Frame must be an integer within the animation")
    with run_lock(output):
        if any(path.name != ".pipeline.lock" for path in output.iterdir()):
            raise PipelineError("Output directory must be empty; use resume for an existing run")
        state = {"schema_version": 1, "run_id": str(uuid.uuid4()), "status": "created",
                 "created_at": utc_now(), "active_seconds": 0.0,
                 "limits": asdict(limits), "paid_usd_spent": 0.0,
                 "frame": frame, "iterations": []}
        session = ActiveSession(output, state)
        write_json(output / "source_spec.json", spec)
        session.save()
        return _render_iteration(session, spec, blender)


def load_state(output: Path):
    state = read_json(output / "state.json")
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise PipelineError("Unsupported or invalid run state")
    try:
        limits = Limits(**state["limits"])
        used = state["active_seconds"]
        # Validate persisted accounting even if the total budget is exhausted.
        import math
        if isinstance(used, bool) or not isinstance(used, (float, int)) or not math.isfinite(used) or used < 0:
            raise ValueError("invalid elapsed time")
        entries = state["iterations"]
        if not isinstance(entries, list) or len(entries) > limits.max_iterations:
            raise ValueError("invalid iteration count")
        for number, entry in enumerate(entries, 1):
            if entry["iteration"] != number or entry["directory"] != f"iteration_{number:03d}":
                raise ValueError("invalid iteration identity")
        if state["paid_usd_spent"] != 0:
            raise ValueError("paid activity is not permitted")
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineError(f"Invalid persisted run state: {exc}") from exc
    return state


def resume_run(output: Path, review_path: Path, blender="blender"):
    output, review_path = output.resolve(), review_path.resolve()
    review = read_json(review_path)
    with run_lock(output):
        state = load_state(output)
        if state["status"] != "review_pending" or not state["iterations"]:
            raise PipelineError(f"Run is {state['status']}; only review_pending runs can resume")
        entry = state["iterations"][-1]
        target = output / entry["directory"]
        # Reject a stale review or changes to the rendered evidence before any mutation.
        spec_path = target / "spec.json"
        if sha256_file(spec_path) != entry["spec_sha256"]:
            raise PipelineError("The iteration spec changed after rendering")
        if set(entry["artifact_sha256"]) != set(ARTIFACTS):
            raise PipelineError("Incomplete persisted artifact evidence")
        if entry["images_sha256"] != {camera: entry["artifact_sha256"][f"{camera}.png"] for camera in CAMERAS}:
            raise PipelineError("Inconsistent persisted image evidence")
        for name, digest in entry["artifact_sha256"].items():
            if name not in ARTIFACTS or sha256_file(target / name) != digest:
                raise PipelineError(f"Rendered evidence changed after rendering: {name}")
        spec = read_json(spec_path)
        validate_spec(spec)
        validate_review(review, state["run_id"], entry)
        revised = apply_patch(spec, review["approved_parameter_patch"]) if review["status"] == "revise" else None
        session = ActiveSession(output, state)
        write_json(target / "review.json", review)
        entry["review_sha256"] = sha256_file(target / "review.json")
        entry["review_status"] = review["status"]
        entry["multiview_validated"] = review["status"] == "accepted"
        entry["status"] = "reviewed"
        state["status"] = review["status"]
        session.save()
        if review["status"] == "accepted":
            state["accepted_iteration"] = entry["iteration"]
            state["accepted_image_sha256"] = entry["image_sha256"]
            state["finished_at"] = utc_now()
            session.save()
        elif review["status"] == "rejected":
            state["stop_reason"] = review["summary"]
            state["finished_at"] = utc_now()
            session.save()
        else:
            return _render_iteration(session, revised, blender)
        return state


def summary(state):
    result = {key: state[key] for key in ("run_id", "status", "active_seconds", "paid_usd_spent")}
    result["render_attempts"] = len(state["iterations"])
    result["limits"] = state["limits"]
    if state["iterations"]:
        latest = state["iterations"][-1]
        result["latest_iteration"] = latest["directory"]
        result["image_sha256"] = latest.get("image_sha256")
        result["images_sha256"] = latest.get("images_sha256")
        result["multiview_validated"] = latest.get("multiview_validated", False)
        if latest.get("error"):
            result["error"] = latest["error"]
    if state.get("stop_reason"):
        result["stop_reason"] = state["stop_reason"]
    if state["status"] == "review_pending":
        result["next_step"] = "Inspect the actual image, complete review.template.json into a new review JSON, then use resume. No visual acceptance is inferred."
    return result
