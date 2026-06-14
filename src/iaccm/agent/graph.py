"""The identification cascade as a LangGraph state machine (docs/method.md).

Nodes:  intake -> triage -> retrieve -> compare -> ask_user (interrupt) -> rank -> record
The ``ask_user`` node uses a human-in-the-loop interrupt to request the one discriminator that
separates the leading candidates (CLAUDE.md rule 4) rather than guessing.

langgraph is imported lazily inside ``build_graph`` so importing this module stays cheap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from ..catalog.models import Candidate, Discriminator, Identification, PartType


class AgentState(TypedDict, total=False):
    # intake
    images: list[Path]
    notes: str
    region: str
    scale_cm: float
    part: PartType
    archetype_ids: list[str]
    # working set
    candidates: list[Candidate]
    pending_discriminator: Discriminator | None
    user_answer: str
    # output
    result: Identification


def build_graph(checkpointer: Any | None = None) -> Any:
    """Construct and compile the cascade graph.

    TODO: implement each node. Required behaviors:
      - retrieve: enumerate the FULL candidate set for ``part`` (Retriever.candidates_for_part);
        assert Retriever.verify_breadth before proceeding.
      - compare: ground the model in rendered candidate plates + notes; never recall from memory.
      - ask_user: emit an interrupt carrying ``pending_discriminator`` and resume on the answer.
      - rank/record: produce an Identification and write an eval/cases/*.yaml regression case.
    """
    from langgraph.graph import END, StateGraph  # lazy import

    graph = StateGraph(AgentState)

    def _todo(name: str):
        def node(state: AgentState) -> AgentState:  # noqa: ARG001
            raise NotImplementedError(f"TODO: implement '{name}' node")

        return node

    for name in ("intake", "triage", "retrieve", "compare", "ask_user", "rank", "record"):
        graph.add_node(name, _todo(name))

    graph.set_entry_point("intake")
    graph.add_edge("intake", "triage")
    graph.add_edge("triage", "retrieve")
    graph.add_edge("retrieve", "compare")
    graph.add_edge("compare", "ask_user")
    graph.add_edge("ask_user", "rank")
    graph.add_edge("rank", "record")
    graph.add_edge("record", END)

    return graph.compile(checkpointer=checkpointer)
