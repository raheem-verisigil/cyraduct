"""Small deterministic LangGraph graph for the Cyraduct integration demo.

No model provider or API key is required: this graph exercises the guarded
tool directly so the security boundary can be tested reproducibly.
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph


class DemoState(TypedDict, total=False):
    action_text: str
    tool_result: str


def build_demo_graph(guarded_tool):
    async def run_guarded_action(state: DemoState) -> DemoState:
        result = await guarded_tool.ainvoke({"action_text": state["action_text"]})
        return {"tool_result": result}

    graph = StateGraph(DemoState)
    graph.add_node("guarded_action", run_guarded_action)
    graph.set_entry_point("guarded_action")
    graph.add_edge("guarded_action", END)
    return graph.compile()
