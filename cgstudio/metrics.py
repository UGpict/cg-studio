"""Deterministic image measurements, never an aesthetic or semantic QA score."""
from __future__ import annotations
from pathlib import Path
import struct
from .io import PipelineError, sha256_file


def image_measurements(path: Path) -> dict:
    try:
        with path.open("rb") as stream:
            header = stream.read(24)
    except OSError as exc:
        raise PipelineError(f"Render image missing: {path}") from exc
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise PipelineError("Renderer did not produce a valid PNG header")
    width, height = struct.unpack(">II", header[16:24])
    if not width or not height:
        raise PipelineError("PNG dimensions must be positive")
    result = {"type": "deterministic_measurements_only", "image_sha256": sha256_file(path),
              "width": width, "height": height, "bytes": path.stat().st_size,
              "quality_verdict": None,
              "limitation": "These values do not establish visual quality, realism, or compliance with the brief."}
    try:
        from PIL import Image, ImageStat
    except ImportError:
        result["pixel_measurements"] = "unavailable (optional Pillow is not installed)"
        return result
    try:
        with Image.open(path) as opened:
            opened.verify()
        with Image.open(path) as opened:
            rgb = opened.convert("RGB")
            # Bounded cost for descriptive measurements even for large input files.
            rgb.thumbnail((1024, 1024))
            gray = rgb.convert("L")
            hist = gray.histogram()
            count = sum(hist)
            result["pixel_measurements"] = {
                "sampling": "whole image resized to fit 1024x1024 with Pillow thumbnail",
                "mean_rgb_0_255": [round(value, 4) for value in ImageStat.Stat(rgb).mean],
                "luma_stddev_0_255": round(ImageStat.Stat(gray).stddev[0], 4),
                "near_black_fraction_luma_lt_5": round(sum(hist[:5]) / count, 6),
                "near_white_fraction_luma_ge_250": round(sum(hist[250:]) / count, 6),
            }
    except Exception as exc:
        raise PipelineError(f"PNG pixel decoding failed: {exc}") from exc
    return result
