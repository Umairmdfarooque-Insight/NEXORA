"""Nexora command line. Usage: python -m app.cli runs|contract <command> ..."""

import argparse
import json
import sys

from app.contracts import business_contract
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

    contract = groups.add_parser("contract", help="Validate BusinessContract files")
    contract_cmds = contract.add_subparsers(dest="command", required=True)
    validate = contract_cmds.add_parser("validate", help="Check a BusinessContract.yaml file")
    validate.add_argument("file")
    schema = contract_cmds.add_parser("schema", help="Print the BusinessContract JSON Schema")
    schema.add_argument("--output", help="Write the schema to this file (UTF-8, LF) instead of printing")

    plan = groups.add_parser("plan", help="Validate a run's ModelSpec.yaml and ExecutionPlan.yaml")
    plan_cmds = plan.add_subparsers(dest="command", required=True)
    plan_validate = plan_cmds.add_parser("validate", help="Check the plan files in a run folder (runs/<run_id>)")
    plan_validate.add_argument("path")
    return parser


def _parse_state(value: str) -> RunState:
    try:
        return RunState(value.upper())
    except ValueError:
        valid = ", ".join(s.value for s in RunState)
        raise ValueError(f"Invalid state: {value!r}. Valid states: {valid}") from None


def _contract_command(args) -> int:
    if args.command == "schema":
        text = json.dumps(business_contract.json_schema(), indent=2) + "\n"
        if args.output:
            # Written as bytes: PowerShell's ">" would save UTF-16.
            with open(args.output, "wb") as handle:
                handle.write(text.encode("utf-8"))
        else:
            print(text, end="")
        return 0
    try:
        business_contract.load(args.file)
    except FileNotFoundError:
        print(f"File not found: {args.file}", file=sys.stderr)
        return 2
    except business_contract.ContractInvalid as exc:
        print("INVALID")
        for issue in exc.issues:
            print(issue)
        return 1
    print("VALID")
    return 0


def _plan_command(args) -> int:
    from pathlib import Path

    from pydantic import ValidationError

    from app.contracts.business_contract import ContractInvalid, load as load_contract
    from app.contracts.feasibility_report import FeasibilityReport
    from app.contracts.metadata_inventory import MetadataInventory
    from app.contracts.model_plan import ExecutionPlan, ModelSpec, load_yaml, to_data
    from app.discovery.plan_validation import validate_plan
    from app.workflow.harvest_stage import canonical_hash

    folder = Path(args.path)
    for name in ("ModelSpec.yaml", "ExecutionPlan.yaml"):
        if not (folder / name).is_file():
            print(f"File not found: {folder / name}", file=sys.stderr)
            return 2
    try:
        model = load_yaml(ModelSpec, folder / "ModelSpec.yaml")
        plan = load_yaml(ExecutionPlan, folder / "ExecutionPlan.yaml")
    except (ValidationError, ValueError) as exc:
        print("INVALID")
        if isinstance(exc, ValidationError):
            for e in exc.errors():
                print(f"  {'.'.join(str(p) for p in e['loc'])}: {e['msg']}")
        else:
            print(f"  {exc}")
        return 1

    inventory = feasibility = contract = None
    if (folder / "MetadataInventory.json").is_file():
        inventory = MetadataInventory.model_validate_json((folder / "MetadataInventory.json").read_text(encoding="utf-8"))
    if (folder / "Feasibility.json").is_file():
        feasibility = FeasibilityReport.model_validate_json((folder / "Feasibility.json").read_text(encoding="utf-8"))
    if (folder / "BusinessContract.yaml").is_file():
        try:
            contract = load_contract(folder / "BusinessContract.yaml")
        except ContractInvalid:
            contract = None
    result = validate_plan(model, plan, inventory, feasibility, contract, canonical_hash(to_data(model)))
    failed = [c for c in result.checks if c.status == "fail"]
    for c in result.checks:
        if c.status == "warning":
            for path in c.evidence.get("paths", [c.description]):
                print(f"  warning {c.id}: {path}")
    if failed:
        print("INVALID")
        for c in failed:
            for path in c.evidence.get("paths", [c.description]):
                print(f"  {c.id}: {path}")
        return 1
    print("VALID")
    return 0


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
    if args.group == "contract":
        return _contract_command(args)
    if args.group == "plan":
        return _plan_command(args)
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
