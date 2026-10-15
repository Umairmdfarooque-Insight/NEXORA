"""Nexora command line. Usage: python -m app.cli runs <command> ..."""

import argparse
import sys

from app.store.base import (
    IllegalTransition,
    RunCorrupt,
    RunNotFound,
    StoreUnavailable,
)
from app.store.factory import get_run_store
from app.workflow.states import RunState

RESUME = "RESUME"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    groups = parser.add_subparsers(dest="group", required=True)

    runs = groups.add_parser("runs", help="Create and inspect runs")
    commands = runs.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create a run and print its run_id")
    create.add_argument("--prompt", required=True)
    create.add_argument("--subject-area")
    create.add_argument("--output", action="append", default=[], dest="outputs")
    create.add_argument("--constraint", action="append", default=[], dest="constraints")

    list_ = commands.add_parser("list", help="List runs, newest first")
    list_.add_argument("--state")

    show = commands.add_parser("show", help="Print a run's manifest")
    show.add_argument("run_id")

    transition = commands.add_parser("transition", help="Move a run to a new state")
    transition.add_argument("run_id")
    transition.add_argument(
        "state", help=f"A run state, or {RESUME} to leave NEEDS_INPUT"
    )
    transition.add_argument("--reason", default="Manual transition")
    return parser


def _parse_state(value: str) -> RunState:
    try:
        return RunState(value.upper())
    except ValueError:
        valid = ", ".join(s.value for s in RunState)
        raise ValueError(f"Invalid state: {value!r}. Valid states: {valid}") from None


def _run_command(args) -> int:
    # Validate arguments before touching the store.
    if args.command == "list" and args.state:
        state_filter = _parse_state(args.state)
    if args.command == "transition":
        target = None if args.state.upper() == RESUME else _parse_state(args.state)

    store = get_run_store()

    if args.command == "create":
        run = store.create(
            args.prompt, args.subject_area, args.outputs, args.constraints
        )
        print(run.run_id)
    elif args.command == "list":
        runs = store.list(state_filter if args.state else None)
        print(f"{'run_id':<36}  {'state':<20}  {'created_at':<20}  prompt")
        for run in runs:
            prompt = " ".join(run.prompt.split())[:40]
            print(
                f"{run.run_id:<36}  {run.state.value:<20}  {run.created_at:<20}  {prompt}"
            )
    elif args.command == "show":
        print(store.get(args.run_id).to_json())
    elif args.command == "transition":
        run = store.transition(args.run_id, target, args.reason, actor="cli")
        print(f"{run.run_id}: {run.state.value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # state messages contain "→"

    args = _build_parser().parse_args(argv)  # bad arguments exit 2
    try:
        return _run_command(args)
    except ValueError as exc:  # bad prompt, bad state name, bad RUN_STORE
        print(exc, file=sys.stderr)
        return 2
    except (RunNotFound, IllegalTransition, RunCorrupt, StoreUnavailable) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
