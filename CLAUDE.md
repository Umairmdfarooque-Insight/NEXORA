# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Nexora is the AI engine behind a UI called "Rayfin" (`APP_NAME` / `UI_APP_NAME` in `app/config.py`). It takes a business requirement in plain English and works out which tables and columns in a Microsoft Fabric Lakehouse can satisfy it. The sample data is AdventureWorks-style (`saleslt` schema).

## Commands

Windows; a virtualenv lives in `.venv` (Python 3.12).

```
.venv\Scripts\activate
pip install -r requirements.txt
pip install pydantic pyodbc      # imported by the code but missing from requirements.txt
python -m app.test_requirement_analyzer   # run one script
```

- There is no build, lint, or pytest setup. The `app/test_*.py` files are **manual scripts** with a `main()`. Each exercises one pipeline stage against live Azure/Fabric.
- Run them as modules from the project root (`python -m app.test_x`). Imports are absolute (`from app.config import ...`), so running the file directly will fail.
- Running anything needs a `.env` (copy `.env.example`). `app/config.py` calls `get_required_setting` at import time for `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` and `AZURE_OPENAI_API_KEY`, so importing `app.config` raises `ValueError` if any is missing. That includes the connector modules. The Fabric settings (`FABRIC_*`) are optional at import time.
- Fabric access uses `InteractiveBrowserCredential`, so every connector run opens a browser login. `fabric_sql_connector` also needs the ODBC Driver 18 for SQL Server installed.

## Architecture

A staged discovery pipeline. There is no orchestrator or entry point yet; the `test_*.py` scripts wire the stages together by hand. Data flows between stages as plain dicts or the `RequirementSpec` pydantic model:

1. `llm/requirement_analyzer.py` — `analyze_requirement()` returns a `RequirementSpec` (objective, entities, metrics, dimensions, filters, security requirements, assumptions, clarification questions).
2. `connectors/fabric_lakehouse.py` + `discovery/metadata_inventory.py` — `build_metadata_inventory()` returns `{schema_name, tables: [{table_name, columns: [{name, data_type}]}], errors}`. It reads the OneLake table REST API with a bearer token for `storage.azure.com`.
3. `discovery/requirement_data_matcher.py` — deterministic matching of requirement terms to inventory columns, driven by the `ALIASES` dict and name normalization.
4. `discovery/semantic_mapper.py` — LLM-suggested mappings and join relationships, given the requirement and the inventory.
5. `discovery/relationship_validator.py` — checks the suggested relationships against the inventory. With `run_data_checks=True` and a connector, it also checks them against real data.
6. `connectors/fabric_sql_connector.py` — a separate read-only path to the Fabric SQL endpoint (pyodbc; passes a `database.windows.net` access token via `attrs_before={1256: ...}`). Used by `discovery/data_profiler.py` and the data checks in step 5.

Design rule stated in the code: **inventory metadata is the source of truth** for which tables and columns exist. LLM output is only a candidate until validated, so don't let LLM-suggested names bypass the validator.

### LLM access

`llm/client.py` builds one shared `OpenAI` client pointed at Azure's v1 endpoint (`{AZURE_OPENAI_ENDPOINT}/openai/v1/`). It uses the Responses API (`client.responses.create`) with `model=AZURE_OPENAI_DEPLOYMENT`. Prompts name the assistant "Nexora"; `ask_rayfin()` is the generic helper. The analyzer and mapper ask for JSON and validate it (pydantic for the analyzer).

## Gotchas

- Table and column names are hardcoded in several places for the sample data (`saleslt.SalesLT_Product`, `saleslt.synthetic_sales_daily`, the `ALIASES` dict, `data_profiler.py`). Generalizing means touching all of them.
- `.env` holds real credentials and is gitignored (`.env.example` lists the variable names).
