"""LangGraph approval interrupt persisted with PostgreSQL checkpoints.

Approval resumes the proposal record only. A clinician still invokes the narrow
application disposition command separately, which rechecks the live case.
"""
import os
from contextlib import contextmanager
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.postgres import PostgresSaver


class ProposalState(TypedDict, total=False):
    case_id: str
    case_version: int
    proposal: dict
    status: str
    human_review: dict


@contextmanager
def approval_graph(database_url):
    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with PostgresSaver.from_conn_string(url) as checkpointer:
        checkpointer.setup()
        def wait_for_human(state):
            decision = interrupt({"reason": "Authorized human review required; proposal does not change clinical state.",
                                  "case_id": state["case_id"], "case_version": state["case_version"], "proposal": state["proposal"]})
            return {"human_review": decision, "status": "review_recorded"}
        builder = StateGraph(ProposalState)
        builder.add_node("human_review", wait_for_human)
        builder.add_edge(START, "human_review")
        builder.add_edge("human_review", END)
        yield builder.compile(checkpointer=checkpointer)


def persist_pause(database_url, thread_id, case_id, case_version, proposal):
    with approval_graph(database_url) as graph:
        result = graph.invoke({"case_id": case_id, "case_version": case_version, "proposal": proposal, "status": "awaiting_human"},
                              {"configurable": {"thread_id": thread_id}})
        return {"thread_id": thread_id, "status": "awaiting_human", "interrupts": len(result.get("__interrupt__", []))}


def resume_review(database_url, thread_id, review):
    with approval_graph(database_url) as graph:
        state = graph.get_state({"configurable": {"thread_id": thread_id}})
        if not state.values:
            raise ValueError("Unknown persisted review thread")
        return graph.invoke(Command(resume=review), {"configurable": {"thread_id": thread_id}})
