# LangGraph

## What it is

LangGraph is a library for building agents as explicit state machines. You declare a
graph: nodes are async functions that update a shared state dict, edges are either
unconditional (`plan -> retrieve`) or conditional (`after plan, go to retrieve, call_tool,
or generate_answer`). The runtime walks the graph until it hits `END`.

That is different from a hidden "agent executor" that loops `LLM -> tool -> LLM` until the
model says it is done. Every branch is code you can draw on a whiteboard.

## Why we use it

- The product question is "should I search the user's documents, run a calculator, or just
  answer?" — three paths, a step budget, and an inspectable trace. A state machine matches
  that better than a prompt-only ReAct loop.
- Conditional edges keep routing in Python (`route_after_plan`, `route_after_evaluate`),
  which is unit-testable without an LLM.
- The same graph grows interrupts for human approval without rewriting the chat route:
  `save_note` calls `interrupt()`; resume uses `Command` on the chat `request_id`.

## What problem it solves

A naive RAG app always retrieves. An unconstrained agent can loop, call anything, and hide
its steps. LangGraph lets us bound the loop (`AGENT_MAX_STEPS`), allowlist tools, and
return only high-level labels (`Analysed request`, `Used calculator tool`) — not the
planner's chain-of-thought.

## Alternatives

| Option | Trade-off |
| --- | --- |
| Always-on RAG (Phase 2) | Simple and predictable; wastes retrieval on greetings and arithmetic |
| LangChain AgentExecutor / ReAct | Fast to demo; control flow lives in the prompt and is hard to test or bound |
| Hand-rolled `if/else` in the route | Fine for two branches; painful once you add evaluate-and-loop |
| CrewAI / AutoGen | Multi-actor metaphors; heavier than one user-facing graph |

## How it is wired in this project

Whiteboard version:

```
START -> plan
           |-- retrieve --> evaluate --\
           |-- call_tool --> evaluate --+--> plan (budget left, no evidence yet)
           |-- generate_answer <-------/
                         |
                        END
```

- `app/agent/state.py` - `AgentState` TypedDict. No reducers: each node returns the keys
  it wants overwritten, including a freshly copied `steps` list.
- `app/agent/routing.py` - `parse_plan` / `decide_plan` / `clamp_decision` and the two
  routers. Invalid JSON falls back to `retrieve` when documents are allowed, otherwise
  `answer`. Unknown tools and `retrieve` with `use_documents=false` are clamped to `answer`.
- `app/agent/nodes.py` - `plan`, `retrieve`, `call_tool`, `evaluate`, `generate_answer`.
  Evaluate is a heuristic (evidence present? both actions tried? budget hit?), not another
  LLM call.
- `app/agent/graph.py` - `StateGraph` compile + `Agent.run()`.
- `app/agent/tools/` - allowlist (`calculator`, `clock`, `save_note`). Execution is MCP
  (`app/mcp/`), not a Python import inside the graph. `save_note` interrupts first.
- `POST /chat` always runs the graph. `GET /agent/tools` lists the allowlist.
  `GET /agent/trace/{request_id}` returns nodes, labels, tool names and chunk counts —
  never questions, answers, document text or planner JSON.
- Prompts: `agent-planner-v1` (JSON action only) and `agent-answer-v1` (tool results).
  Retrieval still uses `rag-system-v1`; plain answers use `chat-system-v1`.

## How I would explain it in an interview

"I treat the agent as a state machine, not a chatty ReAct loop. One node plans with
structured JSON, routing is ordinary Python, retrieve and tools are separate nodes, and
evaluate is a cheap heuristic so I am not spending a model call to decide whether to stop.
The UI only sees high-level steps from the graph. That is the bit I would draw: START,
plan, then retrieve or tool or answer, evaluate, maybe loop, then generate_answer, END —
with a hard step budget."

## Gotchas worth mentioning

- Planner output is untrusted. Clamp after parse: no retrieve when documents are off, no
  tool that is not on the allowlist, no shell.
- Overwrite-style state is easier to explain than annotated reducers, but every node must
  return the *full* list it wants to keep (`steps`, `nodes_visited`), not a delta.
- A garbled plan should fail in a useful direction: retrieve if the user turned documents
  on, otherwise answer. Explicit JSON still wins.
- One LLM call per graph step (plan + answer, plus no LLM for retrieve/tool/evaluate)
  keeps latency and traces predictable.
- Do not put hidden chain-of-thought or full chunks in the activity panel or the trace
  store. Labels only.
- A checkpointer is required for `interrupt()`. We persist to SQLite so a pending write
  still exists after the API process restarts; tests that do not care about durability
  keep `InMemorySaver`.
