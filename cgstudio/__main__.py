"""python -m cgstudio: validate, run, inspect, and resume a review-gated run."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .budget import Limits
from .io import PipelineError, read_json
from .pipeline import load_state, resume_run, start_run, summary
from .spec import validate_spec


def main(argv=None):
    parser = argparse.ArgumentParser(description="CG Studio: bounded local Blender renders with an explicit visual review gate")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate a scene spec without rendering")
    validate.add_argument("--spec", type=Path, required=True)
    run = commands.add_parser("run", help="Render three fixed views, then stop for actual visual review")
    run.add_argument("--spec", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--blender", default="blender", help="Local Blender executable")
    run.add_argument("--frame", type=int, help="Default: spec animation.hero_frame")
    run.add_argument("--max-iterations", type=int)
    run.add_argument("--total-seconds", type=float)
    run.add_argument("--render-seconds", type=float)
    resume = commands.add_parser("resume", help="Apply a hash-bound review; revise only within the approved allowlist")
    resume.add_argument("--output", type=Path, required=True)
    resume.add_argument("--review", type=Path, required=True)
    resume.add_argument("--blender", default="blender")
    status = commands.add_parser("status", help="Read status without launching work")
    status.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            spec = validate_spec(read_json(args.spec))
            print(json.dumps({"status": "valid", "project": spec["project"]}, indent=2))
            return 0
        if args.command == "run":
            budget = validate_spec(read_json(args.spec))["budget"]
            limits = Limits(
                args.max_iterations if args.max_iterations is not None else budget["max_iterations"],
                args.total_seconds if args.total_seconds is not None else budget["total_seconds"],
                args.render_seconds if args.render_seconds is not None else budget["per_render_seconds"], 0)
            state = start_run(args.spec, args.output, args.blender, limits, args.frame)
        elif args.command == "resume":
            state = resume_run(args.output, args.review, args.blender)
        else:
            state = load_state(args.output.resolve())
        print(json.dumps(summary(state), indent=2))
        return 0 if state["status"] in ("accepted", "review_pending") else 2
    except (PipelineError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "error": "Renderer process group terminated"}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
