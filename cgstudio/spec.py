"""Strict scene contract and the small, numeric-only revision surface."""
from __future__ import annotations
import math
import re
from .io import PipelineError


def number(low, high):
    return {"type": "number", "minimum": low, "maximum": high}


def integer(low, high):
    return {"type": "integer", "minimum": low, "maximum": high}


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def vector(low=-100, high=100):
    return {"type": "array", "items": number(low, high), "minItems": 3, "maxItems": 3}


CAMERA_SCHEMA = obj({"position": vector(), "target": vector(), "ortho_scale": number(0.1, 100)})
SPEC_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.invalid/cg-studio/spec.schema.json",
    "title": "CG Studio scene specification",
    **obj({
        "schema_version": {"type": "integer", "const": 1},
        "project": {"type": "string", "minLength": 1, "maxLength": 200},
        "brief": {"type": "string", "minLength": 1, "maxLength": 10000},
        "render": obj({"width": integer(64, 2048), "height": integer(64, 2048), "samples": integer(1, 256),
            "seed": integer(0, 2147483647), "engine": {"type": "string", "const": "CYCLES"},
            "device": {"type": "string", "const": "CPU"}, "denoise": {"type": "boolean"}, "transparent": {"type": "boolean"}}),
        "budget": obj({"max_iterations": integer(1, 3), "total_seconds": {**number(0, 1800), "exclusiveMinimum": 0},
            "per_render_seconds": {**number(0, 180), "exclusiveMinimum": 0}, "max_paid_cost_usd": {"type": "number", "const": 0}}),
        "cup": obj({"outer_radius": number(0.1, 5), "height": number(0.2, 10), "wall_thickness": number(0.005, 0.5),
            "base_thickness": number(0.01, 1), "roughness": number(0, 1), "ior": number(1, 2.5)}),
        "liquid": obj({"fill_height": number(0.01, 10), "roughness": number(0, 1), "ior": number(1, 2.5),
            "transmission": number(0, 1), "absorption_density": number(0, 10), "absorption_color": vector(0, 1),
            "cloudiness": number(0, 1), "meniscus_height": number(0, 0.2), "stream_radius": number(0.005, 0.3),
            "stream_top": number(0.1, 20)}),
        "lighting": obj({"key_energy": number(0, 10000), "fill_energy": number(0, 10000),
            "rim_energy": number(0, 10000), "stream_energy": number(0, 5000), "stream_size": number(0.05, 3), "world_strength": number(0, 10), "exposure": number(-8, 8)}),
        "stage": obj({"card_value": number(0, 1), "card_width": number(0.1, 3), "ground_value": number(0.05, 2)}),
        "animation": obj({"fps": integer(1, 60), "frames": integer(1, 240), "hero_frame": integer(1, 240),
            "mode": {"type": "string", "const": "art_directed_fixed_topology"},
            "fill_start": number(0.01, 10), "fill_end": number(0.01, 10)}),
        "cameras": obj({"hero": CAMERA_SCHEMA, "side": CAMERA_SCHEMA, "top": CAMERA_SCHEMA}),
    }),
}

PATCH_ALLOWLIST = frozenset({
    "cup.roughness", "cup.ior", "liquid.roughness", "liquid.ior", "liquid.transmission",
    "liquid.absorption_density", "liquid.cloudiness", "liquid.meniscus_height", "liquid.stream_radius",
    "lighting.key_energy", "lighting.fill_energy", "lighting.rim_energy", "lighting.world_strength",
    "lighting.exposure", "lighting.stream_energy", "lighting.stream_size", "stage.card_value", "stage.card_width", "stage.ground_value", "render.samples",
})


def validate_schema(value, schema, path="$"):
    expected = schema.get("type")
    matches = {"object": lambda: isinstance(value, dict), "array": lambda: isinstance(value, list),
               "string": lambda: isinstance(value, str), "boolean": lambda: type(value) is bool,
               "number": lambda: type(value) in (float, int) and math.isfinite(value),
               "integer": lambda: type(value) is int}
    if expected and not matches[expected]():
        raise PipelineError(f"{path} must be {expected}")
    if "const" in schema and value != schema["const"]:
        raise PipelineError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise PipelineError(f"{path} must be one of {schema['enum']}")
    if expected == "object":
        required = set(schema.get("required", []))
        missing = required - value.keys()
        if missing:
            raise PipelineError(f"{path} is missing {', '.join(sorted(missing))}")
        properties = schema.get("properties", {})
        unknown = value.keys() - properties.keys()
        if unknown and schema.get("additionalProperties") is False:
            raise PipelineError(f"{path} contains unknown fields: {', '.join(sorted(unknown))}")
        for key, child in value.items():
            if key in properties:
                validate_schema(child, properties[key], f"{path}.{key}")
    elif expected == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")):
            raise PipelineError(f"{path} has invalid length")
        for index, child in enumerate(value):
            validate_schema(child, schema["items"], f"{path}[{index}]")
    elif expected == "string":
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise PipelineError(f"{path} has invalid text format")
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", float("inf")):
            raise PipelineError(f"{path} has invalid text length")
    elif expected in ("number", "integer"):
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            raise PipelineError(f"{path} is outside its permitted range")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise PipelineError(f"{path} must be greater than {schema['exclusiveMinimum']}")


def validate_spec(spec):
    validate_schema(spec, SPEC_SCHEMA)
    cup, liquid, animation = spec["cup"], spec["liquid"], spec["animation"]
    inner_radius = cup["outer_radius"] - cup["wall_thickness"]
    if inner_radius <= 0 or cup["base_thickness"] >= cup["height"]:
        raise PipelineError("Cup wall/base must leave a positive interior")
    if liquid["stream_radius"] >= inner_radius:
        raise PipelineError("Liquid stream must fit inside the cup")
    for label, fill in (("liquid.fill_height", liquid["fill_height"]), ("animation.fill_start", animation["fill_start"]), ("animation.fill_end", animation["fill_end"])):
        if not cup["base_thickness"] < fill < cup["height"] - liquid["meniscus_height"]:
            raise PipelineError(f"{label} and meniscus must fit within the vessel interior")
    if liquid["stream_top"] <= cup["height"]:
        raise PipelineError("Liquid stream_top must be above the cup")
    if animation["hero_frame"] > animation["frames"]:
        raise PipelineError("hero_frame must be within the animation")
    if animation["fill_end"] < animation["fill_start"]:
        raise PipelineError("A pouring animation cannot end with a lower fill level")
    for name, camera in spec["cameras"].items():
        if camera["position"] == camera["target"]:
            raise PipelineError(f"Camera {name} cannot sit at its own target")
    return spec
