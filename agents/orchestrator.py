"""
LangGraph orchestrator: an LLM bound to all tools, looping between
"decide what to call" and "call it" until it has enough to answer.
"""

from __future__ import annotations
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from collections.abc import Sequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from agents.state import AgentState
from agents.tools import ALL_TOOLS
from agents.llm import get_llm
from agents.progress import stream_progress
from agents.errors import tool_node_error

from datetime import date

def build_system_prompt() -> str:
    today = date.today().isoformat()
    return f"""Today's date is {today}. Use this to resolve any relative time
        reference (e.g. "last year", "this season", "the upcoming race") to the
        correct actual year/date — never guess based on your own training data.

        You are an F1 strategy analyst. You have tools split into tiers:

        TIER 1 (fast — try these first): race results, qualifying, pit stops, lap
        times, standings, schedule, and pit-strategy analysis (undercut/overcut).
        These cover most questions, including "why" questions about strategy.

        TIER 2 (slow — only use when Tier 1 genuinely can't answer): tire
        degradation, pace comparison, and raw speed telemetry. Only reach for these
        when the question specifically asks about tire wear, tire compound, or
        lap-level telemetry — not for general strategy or results questions.

        REGULATIONS: use the regulations tool for rules questions (pit stop counts,
        parc fermé, penalties).

        Start broad. Most questions ("what happened in race X", "who's leading the
        championship") are fully answerable from Tier 1 alone. Only escalate to
        Tier 2 when the user's question is specifically about tire physics or asks
        to see raw telemetry — and even then, prefer analyze_pit_strategy first for
        any "why did they pit" style question, since it's usually enough on its own.

        If asked about a future/upcoming race, say clearly that you don't have a
        prediction tool yet — don't guess.

        If a tool returns an error, explain the limitation and use only successful
        results as evidence. Do not invent missing facts. Do not immediately repeat
        rate-limited or failed requests. Ask for corrected inputs when needed.
        If a pace comparison lists missing_drivers, explicitly mention that its
        results cover only the drivers with available clean laps.
        """

_llm = get_llm()
_llm_with_tools = _llm.bind_tools(ALL_TOOLS)


def agent_node(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=build_system_prompt())] + messages
    response = _llm_with_tools.invoke(messages)
    return {"messages": [response]}


tool_node = ToolNode(ALL_TOOLS, handle_tool_errors=tool_node_error)

graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
graph.add_edge("tools", "agent")

app = graph.compile()


def _turn_state(question: str, history: Sequence[BaseMessage] | None) -> AgentState:
    messages = [message.model_copy(deep=True) for message in history or ()]
    messages.append(HumanMessage(content=question))
    return {"messages": messages}


async def chat(
    question: str, history: Sequence[BaseMessage] | None = None
) -> AgentState:
    """Run one turn and return the full conversation state."""
    return await app.ainvoke(_turn_state(question, history))


async def stream_chat(question: str, history: Sequence[BaseMessage] | None = None):
    """Stream progress and a final answer/state, accepting history like chat()."""
    async for event in stream_progress(app, _turn_state(question, history)):
        yield event


async def ask(question: str) -> str:
    """Run a standalone question and return only the final answer text."""
    result = await chat(question)
    return result["messages"][-1].content
