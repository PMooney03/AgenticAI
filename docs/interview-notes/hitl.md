# Human-in-the-loop (LangGraph interrupts)

## What it is

Human-in-the-loop means the agent can *propose* an action that changes state, then wait
for a person to approve or reject it before the action runs. In LangGraph that is
`interrupt()`: the node pauses, the checkpoint is saved, and a later `Command(resume=...)`
restarts the same node with the human's decision.

That is different from logging after the fact. The write does not happen until resume
returns `"approve"`.

## Why we use it

- The job wants responsible-AI controls. Read-only tools (calculator, clock) are safe to
  run immediately. Saving a note writes to disk, so a person has to see the proposal.
- Approval lives in the graph, not in the MCP handler. Even if a prompt-injected document
  talks the planner into `save_note`, the tool still cannot write without a click.
- The same `call_tool` node handles both kinds of tool. The allowlist flag
  `requires_approval` is the only extra branch.

## What problem it solves

A second brain that can write is useful and dangerous. Without an interrupt, a confused
or injected planner could persist junk (or something worse) on every turn. The pause
makes the human the policy engine for writes.

## Alternatives

| Option | Trade-off |
| --- | --- |
| Never give the agent a write tool | Safest; cannot demonstrate HITL |
| Confirm in the UI, then call a separate write API | Works; splits control flow away from the graph |
| LangGraph `interrupt()` + checkpointer | One graph, one thread id, resume is a first-class step |
| Always-on auto-save | Fast; no permission boundary |

## How it is wired in this project

```
plan names save_note
  -> call_tool sees requires_approval
  -> interrupt({tool, description, preview})
  -> POST /chat returns pending_approval (no write yet)
  -> UI ApprovalCard
  -> POST /agent/runs/{request_id}/decision {approved: true|false}
  -> Command(resume="approve"|"reject") on the same thread
  -> call_tool restarts; MCP save_note runs only on approve
```

- Checkpointer: `InMemorySaver` on `app.state` (process-local; enough for a single user).
- Thread id is the chat `request_id`.
- Traces store labels (`Waiting for approval`, `Used save_note tool`) — not the note text.
  The preview is only on `pending_approval` so the human can read it.
- Reject records `"The user rejected this write."` and skips MCP.

## How I would explain it in an interview

"Read-only tools run. Writes pause. LangGraph `interrupt()` checkpoints the graph; the
API returns a pending approval instead of an answer; the UI shows the proposed note;
approve resumes the same thread and only then does the MCP `save_note` handler append
to `notes.jsonl`. Reject never touches disk. The planner cannot bypass that flag."

## Gotchas worth mentioning

- `interrupt()` re-runs the node from the top on resume. Keep everything before the
  interrupt free of side effects.
- A checkpointer is required. No saver, no pause.
- Do not log the note body. Log tool name, approved true/false, and character counts.
- In-memory checkpoints die with the process. That is acceptable locally; a durable
  saver is a Phase 8 concern if the app must survive restarts mid-approval.
