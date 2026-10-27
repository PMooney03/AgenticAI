# RAG (Retrieval-Augmented Generation)

## What it is

RAG gives a language model access to information it was not trained on by retrieving
relevant passages at query time and placing them in the prompt. The model then answers
*from* those passages instead of from memory alone.

```
question -> embed -> vector search -> top-k chunks -> grounded prompt -> LLM -> answer + sources
```

## Why we use it

- The user's documents are private and change often; fine-tuning a model on them is slow,
  expensive, and still hallucinates. Retrieval is instant and always current.
- Answers come with sources (file, page), which the user can verify.
- It is the foundation the agent builds on: in Phase 4 "retrieve" becomes one of several
  actions the agent can choose, instead of something that always happens.

## What problem it solves

LLMs have a knowledge cut-off, no access to private data, and a tendency to fabricate
plausible details. RAG addresses all three by constraining the model to supplied evidence
and making "the documents do not contain this" an acceptable answer.

## Alternatives

| Option | Trade-off |
| --- | --- |
| Fine-tuning | Bakes knowledge into weights; costly, stale quickly, poor at citing sources |
| Long-context stuffing | Put every document in the prompt; simple but slow, expensive and degrades with size |
| Keyword search (BM25) + LLM | Cheap and precise for exact terms; misses paraphrases. Often combined with vectors as "hybrid" |

## How it is wired in this project

- `app/rag/pipeline.py` - `RAGPipeline.answer()`: retrieve, build context, call the LLM,
  extract `[Source N]` citations.
- `app/rag/context.py` - numbers each chunk as `[Source N] file, page P` inside `<<< >>>`
  delimiters and neutralises delimiter look-alikes in document text.
- `app/prompts/rag_system_v1.py` - the grounding rules: answer only from context, cite,
  say when the documents are insufficient, treat excerpts as untrusted data.
- `POST /chat` returns `sources[]` with `cited: true/false` so the UI can distinguish
  "retrieved" from "actually used".

## How I would explain it in an interview

"RAG is retrieval plus prompting. At ingestion I chunk documents and store their embeddings
in Qdrant; at query time I embed the question, pull the closest chunks, and hand them to the
model with strict instructions: answer only from these, cite them, and say so if they don't
contain the answer. The hard parts are not the LLM call - they are chunking well, choosing
k, writing a prompt the model obeys, and measuring whether answers are actually grounded.
That is why I log retrieval and LLM latency separately and track how many retrieved sources
were cited."

## Gotchas worth mentioning

- Chunk size is a trade-off: small chunks are precise but lose context; large ones dilute
  the embedding. A few hundred tokens with overlap is a good default.
- Retrieval always returns *something*; a score threshold or a "no relevant excerpts" path
  is needed so irrelevant chunks don't tempt the model.
- Retrieved text is untrusted input. A document can contain "ignore your instructions";
  the prompt and delimiters exist to resist that (prompt injection).
- Evaluate retrieval and generation separately: did the right chunk come back, and did the
  answer stick to it? (Phase 7 adds this.)
