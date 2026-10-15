import argparse
import contextlib
import io
import json
import sys
import threading
import time
from typing import Callable

CHECK_TIMEOUT_SECONDS = 30
SCHEMA_NAME = "saleslt"
DETAIL_MAX_LENGTH = 200


class CheckFailed(Exception):
    """A check failed for a reason that is already readable."""


def _require_settings(*names: str) -> None:
    import app.config as config

    missing = [name for name in names if not getattr(config, name)]

    if missing:
        raise CheckFailed(f"Missing configuration: {', '.join(missing)}")


def check_llm() -> str:
    from app.config import AZURE_OPENAI_DEPLOYMENT
    from app.llm.client import client

    response = client.responses.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        input="Reply with the word OK.",
        max_output_tokens=256,
    )

    if not response.output_text:
        raise CheckFailed("The AI deployment returned an empty response")

    return "Azure OpenAI replied"


def check_lakehouse() -> str:
    _require_settings(
        "FABRIC_WORKSPACE_ID",
        "FABRIC_LAKEHOUSE_ID",
        "FABRIC_LAKEHOUSE_NAME",
    )

    from app.connectors.fabric_lakehouse import FabricLakehouseConnector

    tables = FabricLakehouseConnector().list_tables(SCHEMA_NAME)

    return f"{len(tables)} tables in {SCHEMA_NAME}"


def check_sql() -> str:
    _require_settings("FABRIC_SQL_SERVER", "FABRIC_SQL_DATABASE")

    from app.connectors.fabric_sql_connector import FabricSQLConnector

    with FabricSQLConnector().connect() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")

        if cursor.fetchone()[0] != 1:
            raise CheckFailed("SELECT 1 returned an unexpected result")

    return "SELECT 1 succeeded"


CHECKS: dict[str, Callable[[], str]] = {
    "llm": check_llm,
    "lakehouse": check_lakehouse,
    "sql": check_sql,
}


def _describe(error: BaseException, secrets: list[str]) -> str:
    if isinstance(error, CheckFailed):
        text = str(error)
    else:
        text = f"{type(error).__name__}: {error}"

    text = " ".join(text.split())

    for secret in secrets:
        text = text.replace(secret, "***")

    return text[:DETAIL_MAX_LENGTH]


def run_check(name: str, secrets: list[str]) -> dict:
    outcome: dict = {}

    def target() -> None:
        try:
            outcome["detail"] = CHECKS[name]()
        except BaseException as error:  # a failing check must not stop the others
            outcome["error"] = error

    started = time.monotonic()
    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(CHECK_TIMEOUT_SECONDS)
    duration_ms = int((time.monotonic() - started) * 1000)

    if worker.is_alive():
        status, detail = "fail", f"timed out after {CHECK_TIMEOUT_SECONDS}s"
    elif "error" in outcome:
        status, detail = "fail", _describe(outcome["error"], secrets)
    else:
        status, detail = "pass", outcome["detail"]

    return {
        "name": name,
        "status": status,
        "duration_ms": duration_ms,
        "detail": detail,
    }


def format_text(results: list[dict]) -> str:
    lines = []

    for result in results:
        seconds = result["duration_ms"] / 1000
        lines.append(
            f"{result['status'].upper():<6}{result['name']:<11}"
            f"{result['detail']} ({seconds:.1f}s)"
        )

    return "\n".join(lines)


def parse_only(value: str | None) -> list[str]:
    if value is None:
        return list(CHECKS)

    names = [part.strip() for part in value.split(",") if part.strip()]
    invalid = [name for name in names if name not in CHECKS]

    if invalid or not names:
        raise ValueError(
            f"Invalid --only value: {value!r}. "
            f"Valid checks: {', '.join(CHECKS)}"
        )

    return list(dict.fromkeys(names))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.tools.smoke",
        description="Check the LLM endpoint, the Lakehouse and the SQL endpoint.",
    )
    parser.add_argument(
        "--only",
        help=f"comma-separated checks to run ({', '.join(CHECKS)})",
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    try:
        names = parse_only(args.only)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    try:
        import app.config as config
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    secrets = [config.AZURE_OPENAI_API_KEY]

    # The connectors print raw API responses while they run; keep them out of the output.
    with contextlib.redirect_stdout(io.StringIO()):
        results = [run_check(name, secrets) for name in names]

    passed = all(result["status"] == "pass" for result in results)

    if args.json:
        print(json.dumps({"passed": passed, "checks": results}, indent=2))
    else:
        print(format_text(results))

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
