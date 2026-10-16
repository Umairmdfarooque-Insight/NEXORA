"""The correlation context of the current work: which run, which stage (T-704, NFR-007).

`run_id` is the correlation ID. It is bound for the duration of a request or a background job and read
by the log formatter, the spans, the metrics and the outbound calls. Work outside a run (`/health`) has
none, and every reader copes with that.
"""

import contextvars
from contextlib import contextmanager

_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("nexora_run_id", default=None)
_stage: contextvars.ContextVar[str | None] = contextvars.ContextVar("nexora_stage", default=None)


def current_run_id() -> str | None:
    return _run_id.get()


def current_stage() -> str | None:
    return _stage.get()


@contextmanager
def bind(run_id: str | None = None, stage: str | None = None):
    """Bind the run and/or the stage for the block; what isn't given keeps its current value."""
    tokens = []
    if run_id is not None:
        tokens.append((_run_id, _run_id.set(run_id)))
    if stage is not None:
        tokens.append((_stage, _stage.set(stage)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
