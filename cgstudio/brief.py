"""Closed, deterministic English/Japanese briefs for the resin benchmark only.

This is a parser, not an LLM or a general scene generator. Every nonempty clause
must be understood. It never renders, executes brief text, calls a service, or
changes a camera, seed, renderer or budget ceiling. Use ``describe`` to inspect
its grammar, parameter bounds, phrase defaults and limitations.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata

from .io import PipelineError, read_json
from .spec import SPEC_SCHEMA, validate_schema, validate_spec

COMPILER = "cgstudio.closed_brief_v1"
DEFAULT_BASE = Path(__file__).resolve().parents[1] / "specs" / "clear_resin.json"
LIMITATIONS = [
    "Only the existing resin-pour benchmark is supported; arbitrary modeling, assets and scene code are unsupported.",
    "English/Japanese phrases use a closed grammar. Unrecognized text blocks compilation; no wording is silently ignored.",
    "Scene lengths are normalized benchmark units, not meters, centimeters or manufacturing dimensions. Initial geometry must also pass the fixed builder-profile constraints in describe.",
    "Animation is art-directed fixed topology, not fluid, particle, chemical or engineering simulation.",
    "Compilation performs no rendering or visual review and cannot certify quality, refraction readability or export appearance.",
    "The base cameras, random seed, renderer, device and nonnumeric settings are preserved. Budget values may only tighten the base limits.",
    "Phrase defaults are documented choices, not inferred measurements. Explicit numeric values override phrase defaults except clear-resin constraints.",
]

# Deliberately distinct from the much smaller review PATCH_ALLOWLIST: these
# values are for a new, initial spec, never for mutating an existing run.
PARAMETER_ALIASES = {
    "render.width": ("render width", "image width", "画像幅"),
    "render.height": ("render height", "image height", "画像高さ"),
    "render.samples": ("samples", "render samples", "サンプル数"),
    "cup.outer_radius": ("cup outer radius", "カップの外半径"),
    "cup.height": ("cup height", "カップの高さ"),
    "cup.wall_thickness": ("wall thickness", "cup wall thickness", "カップの壁厚"),
    "cup.base_thickness": ("base thickness", "cup base thickness", "カップの底厚"),
    "cup.roughness": ("cup roughness", "カップの粗さ"),
    "cup.ior": ("cup ior", "カップの屈折率"),
    "liquid.fill_height": ("fill height", "resin fill height", "液面の高さ"),
    "liquid.roughness": ("resin roughness", "樹脂の粗さ"),
    "liquid.ior": ("resin ior", "樹脂の屈折率"),
    "liquid.transmission": ("resin transmission", "樹脂の透過率"),
    "liquid.absorption_density": ("absorption density", "吸収密度"),
    "liquid.absorption_color": ("absorption color", "吸収色"),
    "liquid.cloudiness": ("cloudiness", "樹脂の濁り"),
    "liquid.meniscus_height": ("meniscus height", "メニスカスの高さ"),
    "liquid.stream_radius": ("stream radius", "流れの半径"),
    "liquid.stream_top": ("stream top", "流れの上端"),
    "lighting.key_energy": ("key energy", "キーライト強度"),
    "lighting.fill_energy": ("fill energy", "フィルライト強度"),
    "lighting.rim_energy": ("rim energy", "リムライト強度"),
    "lighting.stream_energy": ("stream light energy", "流れ用ライト強度"),
    "lighting.stream_size": ("stream light size", "流れ用ライトサイズ"),
    "lighting.world_strength": ("world strength", "環境光強度"),
    "lighting.exposure": ("exposure", "露出"),
    "stage.card_value": ("card value", "カード明度"),
    "stage.card_width": ("card width", "カード幅"),
    "stage.ground_value": ("ground value", "床明度"),
    "animation.fps": ("fps", "フレームレート"),
    "animation.frames": ("frames", "フレーム数"),
    "animation.hero_frame": ("hero frame", "ヒーローフレーム"),
    "animation.fill_start": ("fill start", "開始液面"),
    "animation.fill_end": ("fill end", "終了液面"),
    "budget.max_iterations": ("max iterations", "最大反復数"),
    "budget.total_seconds": ("total seconds", "合計秒数"),
    "budget.per_render_seconds": ("per render seconds", "レンダー毎の秒数"),
    "budget.max_paid_cost_usd": ("max paid cost usd", "有料費用上限usd"),
}

CLEAR = {"liquid.transmission": 1.0, "liquid.cloudiness": 0.0,
         "liquid.roughness": 0.045, "liquid.absorption_density": 0.06,
         "liquid.absorption_color": [0.94, 0.99, 1.0]}
THICK = {"cup.wall_thickness": 0.065, "cup.base_thickness": 0.13,
         "cup.roughness": 0.055, "cup.ior": 1.46}
# These are whole-clause matches. Never add a substring fallback.
PHRASES = [
    ("clear_resin_pour", r"(?:clear|transparent) resin (?:pours|is poured|pouring)(?: continuously)? into (?:a )?(?:thick )?(?:transparent|clear|glass)(?: glass)? (?:cup|vessel)", {**CLEAR, **THICK}, ["continuous_stream", "transparent_cup", "clear_resin"]),
    ("clear_resin_pour", r"pour (?:clear|transparent) resin(?: continuously)? into (?:a )?(?:thick )?(?:transparent|clear|glass)(?: glass)? (?:cup|vessel)", {**CLEAR, **THICK}, ["continuous_stream", "transparent_cup", "clear_resin"]),
    ("clear_resin_pour", r"透明(?:な)?(?:レジン|樹脂)を(?:厚みのある|厚い)?透明(?:な)?(?:カップ|容器)(?:に|へ)(?:注ぐ|注いで|注いでください|注ぎ込む|流し込む)", {**CLEAR, **THICK}, ["continuous_stream", "transparent_cup", "clear_resin"]),
    ("clear_resin", r"(?:clear|transparent) resin|透明(?:な)?(?:レジン|樹脂)", CLEAR, ["clear_resin"]),
    ("thick_transparent_cup", r"(?:a )?thick (?:transparent|clear|glass)(?: glass)? (?:cup|vessel)|(?:厚みのある|厚い)透明(?:な)?(?:カップ|容器)", THICK, ["transparent_cup", "wall_thickness"]),
    ("wall_thickness", r"(?:real|believable|visible) (?:wall )?thickness|実際の壁厚|壁の厚み|厚みを見せる", {}, ["wall_thickness"]),
    ("meniscus", r"(?:a )?(?:clean|visible) meniscus|きれいなメニスカス|メニスカスを見せる", {"liquid.meniscus_height": 0.032}, ["meniscus"]),
    ("free_surface", r"(?:a )?visible free surface|見える自由表面|液面を見せる", {}, ["free_surface"]),
    ("refraction", r"(?:(?:readable|believable|visible) )?refraction|屈折を見せる|読みやすい屈折|自然な屈折", {}, ["refraction"]),
    ("contact_shadows", r"soft (?:contact|grounded) shadows|柔らかい接地影|柔らかい接地影を見せる", {}, ["contact_shadows"]),
    ("metal_witness", r"(?:a )?metal (?:witness (?:object|cylinder)|object for reflection reference)|金属の参照物|反射確認用の金属円柱", {}, ["metal_witness"]),
    ("continuous_stream", r"(?:a )?continuous (?:resin )?stream|連続した(?:樹脂の)?流れ", {}, ["continuous_stream"]),
    ("fixed_cameras", r"(?:keep (?:the )?)?(?:three )?fixed cameras|固定カメラを維持|3つの固定カメラ", {}, ["fixed_cameras"]),
    ("fixed_topology_animation", r"art[- ]directed fixed[- ]topology animation|固定トポロジーの演出アニメーション", {}, ["fixed_topology_animation"]),
    ("no_simulation", r"not a fluid simulation|no fluid simulation|流体シミュレーションではない|流体シミュレーションは使わない", {}, ["fixed_topology_animation"]),
    ("local_cpu", r"local cpu rendering|cycles cpu rendering|ローカルcpuレンダリング", {}, ["local_cpu"]),
    ("no_paid_services", r"no paid (?:api|services)|有料apiは使わない|有料サービスは使わない", {}, ["no_paid_services"]),
]

NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e[+-]?[0-9]+)?"
NUMBER_RE = re.compile(NUMBER, re.IGNORECASE)
ALIAS_TO_PATH = {alias: path for path, aliases in PARAMETER_ALIASES.items() for alias in (path, *aliases)}
ALIAS_PATTERN = "|".join(re.escape(alias) for alias in sorted(ALIAS_TO_PATH, key=len, reverse=True))
ASSIGNMENT = re.compile(rf"(?P<alias>{ALIAS_PATTERN})(?:(?:\s*(?:=|:|は|を)\s*)|(?:\s+is\s+)|\s+)(?P<value>.+?)(?:にする|にしてください)?$")
RESOLUTION = re.compile(r"(?:resolution|render at|解像度)(?:\s*(?:=|:|は|を)\s*|\s+)([0-9]+)\s*[x×]\s*([0-9]+)(?:にする|にしてください)?$")


def _normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _flatten(value, prefix=""):
    flat = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            flat.update(_flatten(child, path))
        else:
            flat[path] = deepcopy(child)
    return flat


def _set(spec, path, value):
    keys = path.split(".")
    target = spec
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = deepcopy(value)


def _parameter_schema(path):
    schema = SPEC_SCHEMA
    for key in path.split("."):
        schema = schema["properties"][key]
    return schema


def _clauses(text):
    """Split only documented separators; keep vector commas and numeric dots."""
    parts, start, depth = [], 0, 0
    for index, char in enumerate(text):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        boundary = char in ";\n。!?" or (char == "." and (index + 1 == len(text) or text[index + 1].isspace()))
        if depth == 0 and (boundary or char in ",、"):
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return [piece.strip() for part in parts for piece in re.split(r"\s+and\s+", part, flags=re.IGNORECASE) if piece.strip()]


def _parse_value(text, schema):
    if schema["type"] == "array":
        # JSON numeric vectors only; no expressions, object keys or constants.
        if not re.fullmatch(rf"\[\s*{NUMBER}\s*,\s*{NUMBER}\s*,\s*{NUMBER}\s*\]", text, re.IGNORECASE):
            raise PipelineError("Use a three-number vector such as [0.94, 0.99, 1.0].")
        values = [float(part.strip()) for part in text[1:-1].split(",")]
        if not all(math.isfinite(value) for value in values):
            raise PipelineError("Every vector number must be finite.")
        return values
    if not NUMBER_RE.fullmatch(text):
        if re.search(r"(?:\b(?:mm|cm|meters?|metres?|inches|feet)\b|ミリ|センチ|メートル)", text):
            raise PipelineError("Physical units are unsupported; use normalized benchmark units.")
        raise PipelineError("Use one finite numeric literal, without units, expressions or code.")
    exact = Decimal(text)
    value = float(exact)
    if not math.isfinite(value):
        raise PipelineError("The number must be finite.")
    if schema["type"] == "integer":
        if exact != exact.to_integral_value():
            raise PipelineError("This parameter requires an integer.")
        return int(exact)
    return value


def _unknown_kind(clause):
    if re.search(r"```|`|__import__|\.system\s*\(|\b(?:python|bash|javascript|exec|eval|subprocess|script|code|import|run command|pip install|sudo|curl)\b|コード|スクリプト|実行|\$\(|&&|\|\|", clause):
        return "unsupported", "executable_request", "Briefs are data. Code, commands, expressions and script requests are unsupported."
    if re.search(r"simulat|\bcfd\b|\bparticles?\b|シミュレーション|物理演算|粘度|硬化|流体", clause):
        return "unsupported", "simulation_request", "The benchmark supports only art-directed fixed-topology motion; simulation and chemistry are unsupported."
    if re.search(r"\bcameras?\b|\bseed\b|カメラ|シード", clause):
        return "unsupported", "fixed_view_request", "Cameras and random seed are fixed to the base spec. Start a separately reviewed scene version for new views."
    if re.search(r"\b(?:gpu|eevee|octane|redshift|paid|cloud render|budget|unlimited|subscription)\b|有料|無制限|予算", clause):
        return "unsupported", "execution_scope", "Renderer/device changes, paid services and budget expansion are unsupported. Only listed budget reductions are allowed."
    if "=" in clause or re.search(r"^[a-z_][a-z0-9_]*\.[a-z_]", clause) or ":" in clause:
        return "unsupported", "unknown_assignment", "Unknown assignment. Use a listed parameter name and one numeric value."
    if re.search(r"\b(?:add|remove|delete|replace|dragon|car|human|character|ocean|logo|text|mesh|asset|model)\b|追加|削除|ドラゴン|人物|海|ロゴ|文字|モデル", clause):
        return "unsupported", "scene_scope", "New objects, removal, assets and arbitrary scene/model changes are outside the resin benchmark."
    return "needs_clarification", "unrecognized_clause", "This entire clause is outside the closed grammar. Restate it using describe's phrases or explicit numeric parameters."


BUILDER_PROFILE_CONSTRAINTS = [
    "cup.wall_thickness > 0.043 keeps the fixed rolled inner lip inside the outer lip.",
    "cup.base_thickness > 0.035 and cup.height - cup.base_thickness > 0.060 retain the fixed base and rim shoulders.",
    "0.86 * cup.outer_radius - cup.wall_thickness - 0.004 > 0 keeps the lower liquid profile radius positive.",
    "cup.outer_radius < 1.17 keeps the vessel clear of the fixed refraction card/markers and metal witness.",
    "Each fill height (liquid.fill_height, animation.fill_start, animation.fill_end) > base_thickness + 0.060 keeps the base shoulder, stream tip and animated surface separate.",
    "Each fill height + meniscus_height + 0.007 < cup.height - 0.035 keeps the ripple/meniscus below the fixed rim shoulder.",
    "At every fill state, the computed liquid outer radius must be less than the true tapered cup inner radius at that height.",
    "hypot(0.235, 0.044) + 1.02 * stream_radius + 0.046 < the smallest computed liquid radius across all fill states bounds the fixed offset, helical wander and stream bulge conservatively.",
    "liquid.stream_top - 0.010 > cup.height + 0.005 keeps the nozzle mouth above the rolled cup rim.",
]


def validate_supported_profile(spec: dict) -> dict:
    """Validate the existing builder's fixed geometric offsets, without rendering.

    This conservative initial/revision guard supplements validate_spec; it does
    not certify manifold output, visual quality, camera framing or simulation.
    Constants mirror scripts/build_scene.py and must be reviewed if it changes.
    """
    validate_spec(spec)
    cup, liquid, animation = spec["cup"], spec["liquid"], spec["animation"]
    r, h, w, b = (cup[key] for key in ("outer_radius", "height", "wall_thickness", "base_thickness"))
    checks = [
        (w > 0.043, "cup.wall_thickness must exceed 0.043 for the fixed rolled lip"),
        (b > 0.035 and h - b > 0.060, "Cup base and rim shoulders need base_thickness > 0.035 and height - base_thickness > 0.060"),
        (0.86 * r - w - 0.004 > 0, "The builder's lower liquid profile radius (0.86 * outer_radius - wall_thickness - 0.004) must be positive"),
        (r < 1.17, "cup.outer_radius must be below 1.17 to clear the fixed diagnostic card and witness"),
        (liquid["stream_top"] - 0.010 > h + 0.005, "The fixed nozzle mouth must be above the rolled cup rim: stream_top - 0.010 > cup.height + 0.005"),
    ]
    for valid, message in checks:
        if not valid:
            raise PipelineError(message)
    radii = []
    for label, z in (("liquid.fill_height", liquid["fill_height"]), ("animation.fill_start", animation["fill_start"]), ("animation.fill_end", animation["fill_end"])):
        if z <= b + 0.060:
            raise PipelineError(f"{label} must exceed cup.base_thickness + 0.060 for fixed base/stream/animation offsets")
        if z + liquid["meniscus_height"] + 0.007 >= h - 0.035:
            raise PipelineError(f"{label} plus meniscus and 0.007 ripple must stay below cup.height - 0.035")
        radius = 0.9 * r - w + (z - b) / (h - b) * (0.1 * r) - 0.004
        inner = 0.9 * r - w + (z - b - 0.025) / (h - b - 0.060) * (0.1 * r)
        if radius >= inner:
            raise PipelineError(f"{label} puts the computed liquid profile outside the fixed tapered cup interior")
        radii.append(radius)
    envelope = math.hypot(0.235, 0.044) + 1.02 * liquid["stream_radius"] + 0.046
    if envelope >= min(radii):
        raise PipelineError("The fixed off-center stream, helical wander and bulge must fit inside the smallest liquid radius across every fill state")
    return spec


def compile_brief(brief: str, base: dict | None = None) -> dict:
    """Return an auditable report; only ``compiled`` contains a runnable spec.

    Invalid base specs raise PipelineError. Brief problems become structured
    issues and never yield a partially interpreted spec. Inputs are not mutated.
    Numeric duplicates must agree; numeric assignments override phrase defaults.
    """
    if not isinstance(brief, str):
        raise PipelineError("The brief must be a string.")
    source = "provided_base" if base is not None else "specs/clear_resin.json"
    baseline = deepcopy(base) if base is not None else read_json(DEFAULT_BASE)
    validate_spec(baseline)
    baseline_flat = _flatten(baseline)
    digest = hashlib.sha256(json.dumps(baseline, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
    issues, recognized, requirements = [], [], []
    numeric, numeric_sources, phrase_values, phrase_sources = {}, {}, {}, {}
    clear_sources = []

    def issue(kind, code, index, text, message):
        issues.append({"kind": kind, "code": code, "clause_index": index, "clause": text, "message": message})

    def numeric_assignment(path, value, index, clause):
        if path.startswith("budget.") and value > baseline_flat[path]:
            issue("unsupported", "budget_expansion", index, clause, f"{path} cannot exceed the base limit {baseline_flat[path]}.")
            return
        try:
            validate_schema(value, _parameter_schema(path), path)
        except PipelineError as exc:
            issue("needs_clarification", "parameter_range", index, clause, str(exc))
            return
        if path in numeric and numeric[path] != value:
            issue("needs_clarification", "contradictory_parameter", index, clause, f"Conflicting values for {path}: {numeric[path]!r} and {value!r}. No precedence is assumed.")
            return
        numeric[path] = value
        numeric_sources.setdefault(path, []).append(index)

    if not brief.strip() or len(brief) > 10000:
        issue("needs_clarification", "brief_length", 0, "", "Provide a nonempty brief of at most 10,000 characters.")
        clauses = []
    else:
        # NFKC allows Japanese full-width numerals/punctuation; original text is
        # still stored verbatim in report/spec. Case is normalized per clause.
        clauses = _clauses(unicodedata.normalize("NFKC", brief))
        if not clauses:
            issue("needs_clarification", "empty_brief", 0, brief, "Provide at least one supported phrase or parameter.")
    for index, clause in enumerate(clauses, 1):
        normalized = _normalize(clause)
        normalized = re.sub(r"^please\s+", "", normalized)
        normalized = re.sub(r"^show\s+", "", normalized)
        resolution = RESOLUTION.fullmatch(normalized)
        assignment = ASSIGNMENT.fullmatch(normalized)
        if resolution:
            values = {"render.width": int(resolution[1]), "render.height": int(resolution[2])}
            for path, value in values.items():
                numeric_assignment(path, value, index, clause)
            recognized.append({"clause_index": index, "clause": clause, "intent": "numeric_resolution", "parameters": values})
            continue
        if assignment:
            path = ALIAS_TO_PATH[assignment["alias"]]
            try:
                value = _parse_value(assignment["value"], _parameter_schema(path))
            except (PipelineError, ValueError, OverflowError, InvalidOperation) as exc:
                kind, code, message = _unknown_kind(assignment["value"])
                if code == "executable_request":
                    issue(kind, code, index, clause, message)
                else:
                    issue("needs_clarification", "invalid_numeric_literal", index, clause, str(exc))
                continue
            numeric_assignment(path, value, index, clause)
            recognized.append({"clause_index": index, "clause": clause, "intent": "numeric_parameter", "parameters": {path: value}})
            continue
        matched = False
        for intent, pattern, values, cues in PHRASES:
            if not re.fullmatch(pattern, normalized):
                continue
            matched = True
            recognized.append({"clause_index": index, "clause": clause, "intent": intent, "parameters": deepcopy(values)})
            for path, value in values.items():
                phrase_values[path] = deepcopy(value)
                phrase_sources.setdefault(path, []).append(index)
            if "clear_resin" in cues:
                clear_sources.append(index)
            for cue in cues:
                if cue not in requirements:
                    requirements.append(cue)
            break
        if not matched:
            kind, code, message = _unknown_kind(normalized)
            issue(kind, code, index, clause, message)

    if clear_sources:
        for path, required in (("liquid.cloudiness", 0), ("liquid.transmission", 1)):
            if path in numeric and numeric[path] != required:
                index = numeric_sources[path][0]
                issue("needs_clarification", "contradictory_intent", index, clauses[index - 1], f"The clear-resin phrase requires {path}={required}; the explicit value disagrees. Remove the phrase or correct the value.")
    requested = {**phrase_values, **numeric}
    candidate = deepcopy(baseline)
    for path, value in requested.items():
        _set(candidate, path, value)
    candidate["brief"] = brief
    if not issues:
        try:
            validate_spec(candidate)
        except PipelineError as exc:
            issue("needs_clarification", "incompatible_parameters", 0, "", str(exc))
        else:
            try:
                validate_supported_profile(candidate)
            except PipelineError as exc:
                issue("needs_clarification", "unsupported_builder_profile", 0, "", str(exc))
    # Unsupported takes priority over clarification, but all issues are retained.
    status = "unsupported" if any(item["kind"] == "unsupported" for item in issues) else ("needs_clarification" if issues else "compiled")
    provenance = {}
    for path in baseline_flat:
        if path == "brief":
            provenance[path] = {"source": "original_brief", "clause_indexes": []}
        elif path in numeric:
            provenance[path] = {"source": "explicit_numeric", "clause_indexes": numeric_sources[path]}
        elif path in phrase_values:
            provenance[path] = {"source": "phrase_default", "clause_indexes": phrase_sources[path]}
        else:
            provenance[path] = {"source": "base", "clause_indexes": []}
    return {
        "schema_version": 1, "compiler": COMPILER, "status": status,
        "brief": brief, "base": {"source": source, "sha256": digest},
        "spec": candidate if status == "compiled" else None,
        "recognized": recognized, "requirements": requirements,
        "requested_parameters": requested,
        "defaults": {path: value for path, value in baseline_flat.items() if path not in requested and path != "brief"},
        "provenance": provenance, "issues": issues,
        "limitations": list(LIMITATIONS),
    }


def describe() -> dict:
    """Machine-readable grammar and complete initial-parameter contract."""
    return {
        "compiler": COMPILER,
        "grammar": {
            "clause_separators": "Semicolon, newline, English/Japanese sentence punctuation, comma, Japanese comma, or the English word 'and'. Vector commas are preserved.",
            "normalization": "Unicode NFKC, case-insensitive English, whitespace collapsed. Optional 'please' and 'show' clause prefixes.",
            "numeric_forms": ["cup.height = 1.8", "cup height is 1.8", "カップの高さは1.8", "解像度は512x512", "absorption color = [0.94, 0.99, 1.0]"],
            "numeric_rules": "Only finite literals. Integers may use integral decimal notation. No expressions or physical units. Duplicates must agree; explicit values override phrase defaults. Clear resin requires transmission=1 and cloudiness=0.",
            "phrase_rules": [{"intent": intent, "full_clause_regex": pattern, "defaults": deepcopy(values), "review_requirements": list(cues)} for intent, pattern, values, cues in PHRASES],
        },
        "builder_profile_constraints": list(BUILDER_PROFILE_CONSTRAINTS),
        "parameters": {path: {"aliases": list(aliases), "schema": deepcopy(_parameter_schema(path)), "budget_reduction_only": path.startswith("budget.")} for path, aliases in PARAMETER_ALIASES.items()},
        "examples": [
            "Clear resin pours into a thick transparent cup. Show real wall thickness, a clean meniscus, readable refraction, soft contact shadows and a metal object for reflection reference. Resolution 512x512; samples=32.",
            "透明なレジンを厚みのある透明なカップに注ぐ。壁の厚み、きれいなメニスカス、屈折を見せる、柔らかい接地影。解像度は512x512。サンプル数は32。",
            "cup.height=1.8; liquid.stream_top=3; animation.fill_start=0.6; animation.fill_end=1.4; budget.max_iterations=1",
        ],
        "result_contract": "status=compiled includes a validated spec. needs_clarification/unsupported include spec=null and all detected issues. No partial output spec is usable. requirements are requests for later actual visual review, not quality assertions.",
        "default_base": "specs/clear_resin.json in the source checkout; use --base for an explicit complete valid spec",
        "provenance": "base.sha256 hashes canonical sorted compact UTF-8 JSON. defaults lists retained base values. provenance covers every spec leaf, distinguishing base, phrase_default, explicit_numeric and original_brief.",
        "cli_outputs": "--output writes a new report JSON (stdout if omitted); --spec-output writes only a compiled spec. Existing files are never overwritten. --base is read-only. Exit 0=compiled/describe, 2=blocked/error.",
        "limitations": list(LIMITATIONS),
    }


def _write_new_json(path, value):
    """Publish a fully-written local file without clobbering previous evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    compile_command = commands.add_parser("compile", help="Compile a closed English/Japanese resin brief without rendering")
    inputs = compile_command.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--brief", help="Brief text; shell-quote it as data")
    inputs.add_argument("--brief-file", type=Path, help="UTF-8 brief text file")
    compile_command.add_argument("--base", type=Path, help="Complete valid base spec; default: specs/clear_resin.json")
    compile_command.add_argument("--output", type=Path, help="New structured report JSON; default: stdout")
    compile_command.add_argument("--spec-output", type=Path, help="New runnable spec JSON, written only on successful compilation")
    describe_command = commands.add_parser("describe", help="Print the complete grammar, parameter bounds, examples and limitations")
    describe_command.add_argument("--output", type=Path, help="New grammar JSON; default: stdout")
    args = parser.parse_args(argv)
    try:
        targets = [path for path in (args.output, getattr(args, "spec_output", None)) if path is not None]
        if len({path.resolve() for path in targets}) != len(targets):
            raise PipelineError("Report and spec outputs must be different files.")
        for path in targets:
            if path.exists() or path.is_symlink():
                raise PipelineError(f"Refusing to overwrite existing output: {path}")
        if args.command == "describe":
            result = describe()
            exit_code = 0
        else:
            brief = args.brief if args.brief is not None else args.brief_file.read_text(encoding="utf-8")
            result = compile_brief(brief, read_json(args.base) if args.base is not None else None)
            exit_code = 0 if result["status"] == "compiled" else 2
            if exit_code == 0 and args.spec_output is not None:
                _write_new_json(args.spec_output, result["spec"])
        if args.output is not None:
            _write_new_json(args.output, result)
        else:
            print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True))
        return exit_code
    except (PipelineError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
