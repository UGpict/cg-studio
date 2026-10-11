"""Explicit review attestation and narrow, auditable parameter revisions."""
from __future__ import annotations
from copy import deepcopy
import math
import re
from .io import PipelineError
from .spec import PATCH_ALLOWLIST, SPEC_SCHEMA, obj, validate_schema, validate_spec

CAMERAS = ("hero", "side", "top")
TEXT = {"type": "string", "minLength": 1, "maxLength": 10000}
HASH = {"type": "string", "minLength": 64, "maxLength": 64, "pattern": "^[0-9a-f]{64}$"}
PATCH_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    path: SPEC_SCHEMA["properties"][path.split('.')[0]]["properties"][path.split('.')[1]]
    for path in sorted(PATCH_ALLOWLIST)
}}
REVIEW_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.invalid/cg-studio/review.schema.json",
    "title": "CG Studio completed visual review",
    **obj({
        "run_id": TEXT, "iteration": {"type": "integer", "minimum": 1, "maximum": 3},
        "image_sha256": HASH, "images_sha256": obj({camera: HASH for camera in CAMERAS}),
        "spec_sha256": HASH, "status": {"type": "string", "enum": ["accepted", "revise", "rejected"]},
        "reviewer": obj({"name": TEXT, "kind": {"type": "string", "enum": ["human", "vision_model"]},
                         "image_inspected": {"type": "boolean", "const": True},
                         "inspected_cameras": {"type": "array", "items": {"type": "string", "enum": list(CAMERAS)}, "minItems": 3, "maxItems": 3}}),
        "summary": TEXT,
        "issues": {"type": "array", "maxItems": 30, "items": obj({
            "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
            "category": {"type": "string", "enum": ["geometry", "material", "lighting", "composition", "animation", "export", "other"]},
            "observation": TEXT, "requested_change": TEXT,
        })},
        "approved_parameter_patch": PATCH_SCHEMA,
    }),
}


def review_template(run_id, entry):
    return {"run_id": run_id, "iteration": entry["iteration"],
            "image_sha256": entry["image_sha256"], "images_sha256": entry["images_sha256"],
            "spec_sha256": entry["spec_sha256"], "status": "pending",
            "reviewer": {"name": "", "kind": "human", "image_inspected": False, "inspected_cameras": []},
            "summary": "Awaiting inspection of the actual rendered images against the spec and QA rubric.",
            "issues": [], "approved_parameter_patch": {}}


def validate_review(review, run_id, entry):
    validate_schema(review, REVIEW_SCHEMA)
    for key in ("run_id", "summary"):
        if not review[key].strip():
            raise PipelineError(f"Review {key} must not be blank")
    if not review["reviewer"]["name"].strip():
        raise PipelineError("Reviewer name must not be blank")
    if review["run_id"] != run_id or review["iteration"] != entry["iteration"]:
        raise PipelineError("Review belongs to another run or iteration")
    for key in ("image_sha256", "spec_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", review[key]) or review[key] != entry[key]:
            raise PipelineError(f"Review {key} does not match rendered evidence")
    if review["images_sha256"] != entry["images_sha256"]:
        raise PipelineError("Review must bind all three exact rendered images")
    if set(review["reviewer"]["inspected_cameras"]) != set(CAMERAS):
        raise PipelineError("Reviewer must inspect hero, side, and top images")
    status, patch, issues = review["status"], review["approved_parameter_patch"], review["issues"]
    for issue in issues:
        if not issue["observation"].strip() or not issue["requested_change"].strip():
            raise PipelineError("Issues require a specific observation and requested change")
    if status == "accepted" and any(issue["priority"] in ("P0", "P1") for issue in issues):
        raise PipelineError("Cannot accept a review with unresolved P0/P1 issues")
    if status != "revise" and patch:
        raise PipelineError("Only a revise decision may include a parameter patch")
    if status == "revise" and (not patch or not issues):
        raise PipelineError("A revise decision requires issues and a nonempty approved parameter patch")
    if status == "rejected" and not issues:
        raise PipelineError("A rejected decision requires at least one issue")
    return review


def apply_patch(spec, patch):
    validate_schema(patch, PATCH_SCHEMA)
    result = deepcopy(spec)
    changes = 0
    for path, value in patch.items():
        if path not in PATCH_ALLOWLIST or type(value) not in (float, int) or not math.isfinite(value):
            raise PipelineError(f"Unapproved or nonnumeric parameter patch: {path}")
        group, key = path.split(".")
        if result[group][key] != value:
            changes += 1
        result[group][key] = value
    if not changes:
        raise PipelineError("Parameter patch makes no actual change")
    validate_spec(result)
    return result
