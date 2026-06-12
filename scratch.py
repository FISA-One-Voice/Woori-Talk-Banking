import asyncio
from langgraph.graph import StateGraph, END
from typing import TypedDict
from langchain_core.runnables import RunnableConfig

class State(TypedDict):
    val: int

def node_a(state):
    return {"val": state["val"] + 1}

sub_builder = StateGraph(State)
sub_builder.add_node("node_a", node_a)
sub_builder.set_entry_point("node_a")
sub_builder.add_edge("node_a", END)
sub_graph = sub_builder.compile()

async def wrapper(state: State, config: RunnableConfig):
    res = await sub_graph.ainvoke(state, config)
    return res

builder = StateGraph(State)
builder.add_node("sub", wrapper)
builder.set_entry_point("sub")
builder.add_edge("sub", END)
graph = builder.compile()

async def main():
    res = await graph.ainvoke({"val": 0})
    print(res)

asyncio.run(main())
