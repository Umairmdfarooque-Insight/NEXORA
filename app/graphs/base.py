"""Shared runner for LangGraph stage graphs (CONTRACTS.md#stage-graphs).

A stage graph only runs the LLM loop inside one stage call. It never changes run state and
has no checkpointer or interrupts. The stage service owns state transitions.
"""

import logging

from langgraph.errors import GraphRecursionError

logger = logging.getLogger(__name__)


class GraphLoopError(RuntimeError):
    """A graph hit its recursion limit. That's a bug, reported as INTERNAL_ERROR."""


def run_graph(
    graph, state: dict, *, run_id: str, stage: str, recursion_limit: int = 25
) -> dict:
    """Invoke `graph` once and return the final state plus `node_path`, the nodes run in order."""
    final = dict(state)
    path: list[str] = []
    config = {
        "recursion_limit": recursion_limit,
        "metadata": {"run_id": run_id, "stage": stage},
    }
    try:
        for chunk in graph.stream(state, config=config, stream_mode="updates"):
            for node, update in chunk.items():
                path.append(node)
                if update:
                    final.update(update)
    except GraphRecursionError:
        logger.error("stage=%s run_id=%s hit the recursion limit", stage, run_id)
        raise GraphLoopError(f"The {stage} graph did not finish") from None
    final["node_path"] = path
    logger.info("stage=%s run_id=%s node_path=%s", stage, run_id, " -> ".join(path))
    return final
