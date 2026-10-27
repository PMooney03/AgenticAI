# React, TypeScript and Vite

## What they are

- **React** is a UI library: you describe the screen as a tree of components that re-render
  when state changes. We use function components and hooks (`useState`, `useEffect`,
  `useCallback`) rather than class components.
- **TypeScript** adds static types so the UI contract matches the FastAPI Pydantic models
  (`DocumentRecord`, `ChatResponse`, `Source`). A renamed API field fails at compile time,
  not in the browser.
- **Vite** is the build tool and dev server. It serves native ES modules in development
  (instant HMR) and rolls a production bundle with `npm run build`.

## Why we use them

The job description asks for a frontend that can display sources, workflow events and
human-approval cards. React is the default for that kind of interactive layout; Vite is the
fastest way to get a typed SPA without a heavy framework (Next.js would add routing and a
Node server we do not need for a local app).

## What problem they solve

A raw HTML page cannot keep document lists, loading states, citation highlighting and a
collapsible activity panel in sync. Components plus typed API calls do.

## Alternatives

| Option | Trade-off |
| --- | --- |
| Next.js / Remix | SSR, routing, deployment story; overkill for a local single-page tool |
| Vue / Svelte | Equally capable; smaller hiring overlap than React |
| Streamlit / Gradio | Fastest demo; not a portfolio-quality UI and hard to show sources/approvals well |
| Create React App | Deprecated; Vite replaced it |

## How it is wired in this project

- `frontend/src/api/client.ts` - one `createClient()` with injectable `fetch` (tests mock
  it). Sends `X-Request-ID`, parses FastAPI error bodies into `ApiError`.
- `frontend/src/hooks/` - `useDocuments`, `useChat`, `useHealth` own server state. The
  chat hook is stateless against the backend: it resends the last 20 turns as `history`.
- `Sidebar` - upload (click or drop), status badges, confirm-to-delete.
- `Chat` - user/assistant bubbles, loading state, `[Source N]` rendered as buttons that
  highlight the matching card.
- `SourcePanel` - filename, page, cosine score, cited vs retrieved, expandable snippet.
- `AgentActivity` - high-level events derived from the response (`Retrieved 4 chunks`).
  Phase 4 will replace the derivation with the LangGraph trace. Hidden chain-of-thought
  is never shown.
- `ApprovalCard` - present but unused until Phase 6.
- CORS on the backend (`CORS_ORIGINS`) plus `VITE_API_BASE_URL` so the UI can talk to
  whatever port the API is on.

## How I would explain it in an interview

"The UI is a thin client over the FastAPI contract. I kept the API client injectable so
component tests never need a running backend, and I split citations in the answer into
buttons that select the corresponding source card. The activity panel is deliberately
dumb in Phase 3: it only reports facts the API already returns (mode, chunk count), which
is the same information I will later stream from LangGraph nodes. That keeps the
responsible-AI rule — no hidden reasoning on screen — in place from day one."
