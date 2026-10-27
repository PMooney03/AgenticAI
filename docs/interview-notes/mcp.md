# MCP (Model Context Protocol)

## What it is

MCP is an open protocol for connecting a language-model app to tools, resources and
prompts. The app is a *client*; tools live on a *server*. They talk JSON-RPC:
`tools/list`, `tools/call`. The agent does not import `os.system` or a Python function
by name — it asks a server to run a named tool with arguments.

That is the same idea as a browser talking HTTP to an API instead of calling a database
driver from the UI.

## Why we use it

- The job description names MCP. Using the official Python SDK (`mcp` 2.x, `MCPServer` +
  `Client`) is how you show you have actually wired it, not just mentioned it.
- Tools stay replaceable. Today's calculator and clock run in-process; tomorrow the same
  client can point at a stdio server or, on Azure, a hosted tool catalog — the graph does
  not change.
- The allowlist stays in *our* code. Even if a server exposed extra tools, the planner
  cannot name them and `execute_tool` refuses them before `tools/call`.

## What problem it solves

Without a protocol, every new capability is another Python import inside the agent.
That does not scale, is hard to sandbox, and mixes orchestration with implementation.
MCP is the seam: the graph decides *whether* to call a tool; the server decides *how*.

## Alternatives

| Option | Trade-off |
| --- | --- |
| Call Python functions from the graph | Simplest; tools are glued to the process and not portable |
| LangChain `@tool` + AgentExecutor | Convenient; hides the protocol and the control flow |
| OpenAI function calling only | Vendor-specific JSON schema; no standard server to reuse |
| Unrestricted shell | Fast demo; unacceptable for a second-brain that reads your files |

## How it is wired in this project

```
planner JSON {action: tool, tool_name, tool_args}
  -> clamp against app/agent/tools/policy.py allowlist
  -> InProcessMCPClient.call_tool
  -> MCP Client(server)  (initialize + tools/call)
  -> MCPServer handlers (calculator AST, clock ISO time)
  -> text result back into LangGraph state
```

- `app/mcp/server.py` - `MCPServer("agentic-second-brain")` with two read-only tools.
- `app/mcp/client.py` - `InProcessMCPClient` uses `async with Client(server)`.
- `python -m app.mcp` - the same server over stdio, so you can attach an external MCP
  inspector or a future subprocess client.
- Calculator errors become MCP `is_error` (`ToolError`); the graph records the message
  and still answers. There is no shell tool. Write tools wait for Phase 6 approval.

## How I would explain it in an interview

"MCP is how the agent uses tools without owning their implementations. I run a local
MCP server with an allowlist — calculator and a clock today, both read-only. The
LangGraph `call_tool` node goes through an MCP client, not a Python import. In the
FastAPI process I use the SDK's in-memory transport so tests and the app speak real
MCP without a second process; `python -m app.mcp` is the stdio form of the same
server. The planner still cannot invent a tool name."

## Gotchas worth mentioning

- Listing tools from the server is not enough. Keep an application allowlist so a
  misconfigured or future MCP server cannot widen the agent's power.
- In-memory `Client(server)` is real MCP, not a fake. Stdio is the same handlers with
  a different transport.
- Tool results are untrusted data in the answer prompt, same as retrieved chunks.
- `requires_approval` is already on the tool spec; Phase 6 will interrupt before
  anything that changes state actually runs.
- On Windows the SDK's stdio module imports `pywintypes`. We add
  `pywin32_system32` to the DLL search path and import MCP during FastAPI startup
  on the main thread, because the first import inside a dependency threadpool
  otherwise raises `ModuleNotFoundError`.
