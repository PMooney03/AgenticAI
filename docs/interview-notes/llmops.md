# LLMOps (metrics and evaluation)

## What it is

LLMOps is the operational loop around an LLM app: version what you ship, observe live
traffic, and evaluate quality on a fixed dataset so a prompt or model change is a
measured decision rather than a vibe.

In this project that means three layers:

1. Prompt versions already on every response (`rag-system-v1`, `agent-planner-v1`, ...).
2. Online metrics: latency, tokens, retrieval, tools, HITL, citation rate, groundedness.
3. Offline eval: a golden set that runs the real LangGraph with fakes, no Ollama.

## Why we use it

- "It seems better" is not an interview answer. You need a number for retrieval and a
  number for generation, because they fail independently.
- Paid tracing (LangSmith, etc.) is out of scope. The same signals fit in-process here
  and map onto Prometheus later.
- The golden set is what CI runs: deterministic, fast, no GPU.

## What problem it solves

RAG can retrieve the right chunk and still hallucinate, or cite nothing, or refuse when
the answer is sitting in context. Agent graphs can take the wrong branch. Without a
harness you only find that by clicking around. Metrics tell you the live mix (how often
we retrieve, how often we refuse, p95 LLM time); eval tells you a change did not break
the known cases.

## Alternatives

| Option | Trade-off |
| --- | --- |
| LLM-as-judge | Flexible; slow, non-deterministic, circular (a model grading a model) |
| LangSmith / Phoenix | Great UX; extra service, often paid, not local-first |
| Exact string match on answers | Brittle the moment the model paraphrases |
| Lexical overlap + citations + routing checks (chosen) | Cheap, explainable, good enough as a proxy; misses fluent-but-wrong paraphrases |
| Human review only | Highest quality; does not scale to every commit |

## How it is wired in this project

```
live chat
  -> score_quality(answer, chunks, citations)   # numbers only
  -> MetricsStore (in-process)
  -> GET /metrics

golden cases (pinned planner JSON + answers + short docs)
  -> same Agent + FakeLLM + FakeEmbeddings + Qdrant :memory:
  -> POST /eval/run  or  python -m app.eval
  -> EvalReport (pass/fail per check, no question/answer text)
```

Quality scores (shared by online and offline):

- **citation_rate** — cited sources / retrieved chunks. `None` on refusal or when nothing
  was retrieved (not applicable, so it does not drag the average down).
- **groundedness** — fraction of content words in the answer that also appear in the
  evidence (chunk text and tool output). A refusal scores 1.0: that is the instructed
  behaviour, not a failed generation.
- **refused** — the allowed "documents do not contain enough information" phrase.

The golden set covers retrieve-and-cite, refuse, calculator, clock, plain answer, and
HITL `save_note` (pause then approve). Checks are routing, retrieval hit, citation,
refusal, tool output, and "did the note actually hit disk".

`GET /metrics` and the UI LLMOps panel never include message bodies. Eval reports use
case ids (`retrieve_leave`) and check names (`cited`, `nodes`).

## How I would explain it in an interview

"I split retrieval from generation. Hit@k on a golden question tells me the chunk came
back; citation rate and lexical overlap tell me the answer used it; a pinned refusal
case tells me the model can still say 'I don't know'. Live metrics are the same scores
plus latency and token totals, kept in process so there is no extra vendor. I would
swap the store for Prometheus histograms without changing what I measure. I am not using
an LLM-as-judge locally because it is slow, expensive, and grades in the same failure
mode I am trying to catch."

## Gotchas worth mentioning

- Overlap is a proxy. "twenty five" vs "25" looks ungrounded even when the fact is
  right. That is why the golden answers use the same wording as the docs.
- Always-on retrieve returns *something*; refusal must still be a first-class case.
- Do not put answers in metrics stores or eval reports if the rest of the app treats
  content as sensitive.
- Online metrics and offline eval answer different questions. A perfect golden set with
  a collapsing p95 is still a production incident.
- Fake embeddings make lexical retrieval succeed. A live-model nightly (not this phase)
  is how you catch 'the 14b model stopped citing'.
