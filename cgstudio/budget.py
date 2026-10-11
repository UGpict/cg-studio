"""Hard local-only limits and renderer process-group termination."""
from __future__ import annotations
from dataclasses import dataclass
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from .io import PipelineError


@dataclass(frozen=True)
class Limits:
    max_iterations: int = 3
    total_seconds: float = 1800.0
    render_seconds: float = 180.0
    paid_usd: float = 0.0

    def __post_init__(self):
        if type(self.max_iterations) is not int or not 1 <= self.max_iterations <= 3:
            raise PipelineError("max_iterations must be an integer from 1 to 3")
        for key, maximum in (("total_seconds", 1800), ("render_seconds", 180)):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
                raise PipelineError(f"{key} must be greater than 0 and at most {maximum}")
        if isinstance(self.paid_usd, bool) or self.paid_usd != 0:
            raise PipelineError("Paid services are disabled: paid_usd must be 0")

    def render_timeout(self, used_seconds: float) -> float:
        if not isinstance(used_seconds, (int, float)) or isinstance(used_seconds, bool) or not math.isfinite(used_seconds) or used_seconds < 0:
            raise PipelineError("Invalid persisted elapsed time")
        remaining = self.total_seconds - used_seconds
        if remaining <= 0:
            raise BudgetExceeded("Total active execution budget exhausted")
        return min(self.render_seconds, remaining)


class BudgetExceeded(PipelineError):
    pass


def run_renderer(command: list[str], log_path: Path, timeout: float) -> dict:
    """Run a local subprocess. On deadline, kill the complete POSIX process group.

    No shell, remote renderer, model API, or paid endpoint is invoked here.
    """
    if os.name != "posix":
        raise PipelineError("Bounded process-tree rendering currently requires POSIX (Linux/macOS)")
    if not math.isfinite(timeout) or timeout <= 0:
        raise BudgetExceeded("No renderer time remains")
    started = time.monotonic()
    with log_path.open("wb") as log:
        try:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            raise PipelineError(f"Renderer could not start: {exc}") from exc
        try:
            code = process.wait(timeout=timeout)
        except BaseException as exc:
            # A renderer can start child workers. Killing only its parent leaks work.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            if isinstance(exc, subprocess.TimeoutExpired):
                raise BudgetExceeded(f"Renderer killed after {timeout:.3f}s deadline") from exc
            raise
    return {"returncode": code, "seconds": round(time.monotonic() - started, 6)}
