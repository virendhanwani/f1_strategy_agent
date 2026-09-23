from langchain_core.messages import HumanMessage
from agents.state import AgentState

state: AgentState = {
    "messages": [HumanMessage(content="who won the 2023 Monaco GP")],
}
print(state)
