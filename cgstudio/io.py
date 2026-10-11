"""Strict JSON and atomic persistence helpers."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile


class PipelineError(Exception):
    """A user-actionable pipeline error."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PipelineError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path):
    def invalid_constant(value):
        raise PipelineError(f"Invalid JSON number: {value}")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=invalid_constant)
    except (OSError, ValueError) as exc:
        raise PipelineError(f"Cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
