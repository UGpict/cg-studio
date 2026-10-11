"""Optional bounded local vision → review → numeric revision runner.

Usage: python -m cgstudio.auto --output runs/shot [--provider-config local.json]
Without an explicit local provider, existing renders remain review_pending.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
import math
from pathlib import Path
import time

from .io import PipelineError, read_json, write_json
from .pipeline import ROOT, load_state, resume_run, run_lock, summary, utc_now
from .vision import LocalVisionProvider, ReviewLimits, load_references, prepare_request, reference_payloads, validate_response


@contextmanager
def adapter_lock(output):
    import fcntl
    with (output / ".vision.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineError("This run already has an active vision adapter") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _result(state, status, reason, provider=None, ledger=None):
    return {"pipeline": summary(state), "adapter": {
        "status": status, "reason": reason,
        "provider_id": provider.provider_id if provider else None,
        "scope": "test_double_only" if provider and provider.kind == "test_double" else "three_view_still_look_only",
        "calls": len(ledger["attempts"]) if ledger else 0,
        "paid_cost_usd": 0,
    }}


def _ledger(output, provider, limits, state, references):
    path = output / "vision_ledger.json"
    if not path.exists():
        return {"schema_version": 1, "run_id": state["run_id"], "provider_fingerprint": provider.fingerprint,
                "provider_id": provider.provider_id, "kind": provider.kind,
                "limits": asdict(limits), "references": references, "attempts": []}
    ledger = read_json(path)
    if (not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or
            ledger.get("run_id") != state["run_id"] or ledger.get("provider_fingerprint") != provider.fingerprint or
            ledger.get("limits") != asdict(limits) or ledger.get("kind") != provider.kind or ledger.get("references") != references):
        raise PipelineError("Persisted vision configuration cannot be changed to reset its allowance")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list) or len(attempts) > limits.max_calls:
        raise PipelineError("Invalid persisted vision attempt count")
    for number, attempt in enumerate(attempts, 1):
        if (not isinstance(attempt, dict) or attempt.get("number") != number or
                type(attempt.get("iteration")) is not int or not 1 <= attempt["iteration"] <= 3 or
                attempt.get("status") not in ("started", "invalid", "completed") or
                type(attempt.get("charged_seconds")) not in (int, float) or
                not math.isfinite(attempt["charged_seconds"]) or attempt["charged_seconds"] < 0 or
                attempt.get("paid_cost_usd") != 0):
            raise PipelineError("Invalid persisted vision attempt accounting")
    return ledger


def run_unattended(output: Path, provider=None, *, limits=None, blender="blender", test_fixture_only=False, references=None):
    """Continue an existing rendered run. Does not install, discover, or call APIs.

    Limits are persisted; uncertain interrupted calls block automatic retries.
    Actual provider elapsed time is also charged against the original render
    run's total active-time ceiling. No hidden time or cost allowance is added.
    """
    output = Path(output).resolve()
    limits = limits or ReviewLimits()
    state = load_state(output)
    if provider is not None and not isinstance(provider, LocalVisionProvider):
        raise PipelineError("Provide an explicitly configured LocalVisionProvider")
    if state["status"] != "review_pending":
        return _result(state, "stopped", "Pipeline already reached its existing stopping condition", provider)
    if provider is None:
        return _result(state, "review_pending", "No local vision provider configured; no visual review or paid call was performed")
    if (provider.kind == "test_double") != test_fixture_only:
        raise PipelineError("Test doubles require explicit test_fixture_only mode; production evidence is forbidden")
    references = [] if references is None else references
    reference_payloads(references)
    reference_identity = [{"label": ref["label"], "sha256": ref["sha256"], "source_url": ref["source_url"]} for ref in references]
    with adapter_lock(output):
        ledger = _ledger(output, provider, limits, state, reference_identity)
        while True:
            with run_lock(output):
                state = load_state(output)
                if state["status"] != "review_pending":
                    return _result(state, "stopped", "Pipeline reached its existing stopping condition", provider, ledger)
                if any(a["status"] == "started" for a in ledger["attempts"]):
                    return _result(state, "review_pending", "An interrupted provider attempt has an uncertain outcome; automatic retry is blocked", provider, ledger)
                entry = state["iterations"][-1]
                previous = [a for a in ledger["attempts"] if a["iteration"] == entry["iteration"]]
                if any(a["status"] == "completed" for a in previous):
                    return _result(state, "review_pending", "A validated review is already saved; inspect its receipt and resume explicitly", provider, ledger)
                used = sum(a["charged_seconds"] for a in ledger["attempts"])
                remaining = min(limits.total_seconds - used, state["limits"]["total_seconds"] - state["active_seconds"])
                if len(ledger["attempts"]) >= limits.max_calls or len(previous) >= limits.attempts_per_iteration or remaining <= 0:
                    return _result(state, "review_pending", "Reviewer call/retry/time allowance exhausted; visual acceptance remains pending", provider, ledger)
                request = prepare_request(output, state, test_fixture_only=test_fixture_only, references=references)
                request["provider_id"] = provider.provider_id
                request["limits"] = asdict(limits)
                request["acceptance_criteria"] = (ROOT / "qa" / "acceptance_criteria.md").read_text(encoding="utf-8")
                timeout = min(limits.per_call_seconds, remaining)
                attempt = {"number": len(ledger["attempts"]) + 1, "iteration": entry["iteration"],
                           "request_id": request["request_id"], "status": "started", "started_at": utc_now(),
                           "charged_seconds": timeout, "timeout_seconds": timeout, "paid_cost_usd": 0}
                ledger["attempts"].append(attempt)
                # Reserve before launch. A process kill cannot restore the allowance.
                state["active_seconds"] += timeout
                state["updated_at"] = utc_now()
                write_json(output / "state.json", state)
                write_json(output / "vision_ledger.json", ledger)
            started = time.monotonic()
            review, failure = None, None
            try:
                response = provider.invoke(request, timeout)
                review = validate_response(response, request, provider, state, limits)
            except Exception as exc:
                # Do not persist untrusted provider stderr, prompts or raw output.
                failure = str(exc) if isinstance(exc, PipelineError) else f"Provider failure: {type(exc).__name__}"
            elapsed = time.monotonic() - started
            with run_lock(output):
                latest = load_state(output)
                if latest["run_id"] != state["run_id"]:
                    raise PipelineError("Run identity changed during review")
                latest["active_seconds"] = max(0, latest["active_seconds"] - timeout + elapsed)
                latest["updated_at"] = utc_now()
                attempt.update(charged_seconds=elapsed, finished_at=utc_now(), status="invalid" if failure else "completed")
                if failure:
                    attempt["error"] = failure
                if review is not None:
                    # Revalidate exact files and iteration immediately before saving.
                    if latest["status"] != "review_pending" or latest["iterations"][-1]["iteration"] != entry["iteration"]:
                        failure = "Pipeline changed while the provider was running; response was discarded"
                    else:
                        try:
                            prepare_request(output, latest, test_fixture_only=test_fixture_only, references=references)
                        except PipelineError as exc:
                            failure = str(exc)
                    if failure:
                        attempt.update(status="invalid", error=failure)
                        review = None
                review_path = output / entry["directory"] / f"vision_review_{attempt['number']:03d}.json"
                if review is not None:
                    write_json(review_path, review)
                    attempt["review_file"] = str(review_path.relative_to(output))
                write_json(output / "state.json", latest)
                write_json(output / "vision_ledger.json", ledger)
                state = latest
            if review is None:
                if state["status"] != "review_pending":
                    return _result(state, "stopped", failure or "Pipeline changed during review", provider, ledger)
                continue
            # Existing resume gate rechecks all evidence, schema, patch safety and budgets.
            try:
                state = resume_run(output, review_path, blender)
            except PipelineError as exc:
                return _result(load_state(output), "review_pending", f"Validated review was saved but could not resume: {exc}", provider, ledger)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider-config", type=Path, help="Explicit trusted local executable config; no API/credential discovery")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--reference-config", type=Path, help="Optional explicit labeled/hash-bound local PNG/JPEG references")
    parser.add_argument("--test-fixture-only", action="store_true", help="Requires marked test-double evidence; never production acceptance")
    parser.add_argument("--max-calls", type=int, default=6)
    parser.add_argument("--attempts-per-iteration", type=int, default=2)
    parser.add_argument("--per-call-seconds", type=float, default=60)
    parser.add_argument("--total-review-seconds", type=float, default=180)
    args = parser.parse_args(argv)
    try:
        provider = LocalVisionProvider.from_file(args.provider_config) if args.provider_config else None
        limits = ReviewLimits(max_calls=args.max_calls, attempts_per_iteration=args.attempts_per_iteration,
                              per_call_seconds=args.per_call_seconds, total_seconds=args.total_review_seconds)
        result = run_unattended(args.output, provider, limits=limits, blender=args.blender,
                                test_fixture_only=args.test_fixture_only,
                                references=load_references(args.reference_config) if args.reference_config else None)
        print(json.dumps(result, indent=2))
        return 0 if result["pipeline"]["status"] in ("accepted", "review_pending") else 2
    except (PipelineError, OSError) as exc:
        print(json.dumps({"error": str(exc), "visual_acceptance": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
