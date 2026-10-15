"""RunStore interface and its errors.

The store is the only code that persists run manifests. The run layer of the
hybrid orchestration (CONTRACTS.md#stage-graphs) goes through it.
"""

from typing import Protocol

from app.workflow.run import IllegalTransition, Run  # noqa: F401  (re-exported)
from app.workflow.states import RunState


class RunNotFound(Exception):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Run not found: {run_id}")


class RunCorrupt(Exception):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Run manifest is corrupt: {run_id}")


class StoreUnavailable(Exception):
    """The backing store can't be reached or refused the request."""


class RunStore(Protocol):
    def create(
        self,
        prompt: str,
        subject_area: str | None = None,
        desired_outputs=(),
        constraints=(),
    ) -> Run: ...

    def get(self, run_id: str) -> Run:
        """Raises RunNotFound or RunCorrupt."""
        ...

    def list(self, state: RunState | None = None, limit: int = 50) -> list[Run]:
        """Newest first. Corrupt runs are skipped with a warning."""
        ...

    def save(self, run: Run) -> None: ...

    def transition(
        self,
        run_id: str,
        to: RunState | None,
        reason: str,
        actor: str = "system",
    ) -> Run:
        """Raises RunNotFound or IllegalTransition(from_, to).

        `to=None` leaves NEEDS_INPUT for the stored resume_state.
        """
        ...
