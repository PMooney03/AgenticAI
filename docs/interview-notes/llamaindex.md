# LlamaIndex

## What it is

LlamaIndex is a data framework for LLM applications. Its strengths are the *data side* of
RAG: loading documents of many formats (readers), splitting them into nodes with metadata
(node parsers), building indexes, and querying them. It can also run whole RAG pipelines
end to end (`VectorStoreIndex`, query engines), which overlaps with LangChain.

## Why we use it (and exactly where)

We use LlamaIndex for **ingestion only**, in two places where it clearly earns its keep:

1. `PDFReader` (`app/ingestion/loaders.py`) - returns one `Document` per PDF page with a
   `page_label`. Page-level granularity is what lets answers cite "report.pdf, page 7".
2. `SentenceSplitter` (`app/ingestion/chunking.py`) - splits text into chunks within a
   token budget while respecting sentence and paragraph boundaries, with configurable
   overlap. Better than fixed character windows and not worth re-implementing.

We deliberately do **not** use `VectorStoreIndex`, LlamaIndex's Qdrant integration, or its
query engines. Those would hide the embed / upsert / search steps inside the framework; we
keep them explicit in our own code so each step can be tested, logged and explained.

TXT and Markdown files are read with `Path.read_text` because a reader adds nothing there.

## What problem it solves

Getting clean, well-chunked text with metadata out of real-world files is tedious and full
of edge cases (encodings, page labels, sentence boundaries). LlamaIndex has already solved
those well.

## Alternatives

| Option | Trade-off |
| --- | --- |
| LangChain document loaders + `RecursiveCharacterTextSplitter` | Similar capability; character-based splitting is cruder than sentence-aware splitting |
| Unstructured.io | Excellent layout-aware parsing (tables, headings); heavy dependencies |
| Hand-rolled `pypdf` + regex | Full control, no framework; you re-implement sentence splitting and overlap |
| Docling / Marker | State-of-the-art PDF-to-Markdown; large models, slower |

## LlamaIndex vs LangChain in this project

| Concern | Tool |
| --- | --- |
| Document loading and chunking | LlamaIndex |
| LLM client, prompts, tool definitions, structured output | LangChain |
| Orchestration / agent state machine | LangGraph (Phase 4) |
| Embedding, vector store, retrieval logic | Our own code over Ollama and Qdrant |

## How I would explain it in an interview

"LlamaIndex is strongest on the data pipeline, so that is the only place I use it: a PDF
reader that preserves page numbers and a sentence-aware splitter with overlap. I stopped
there on purpose. Letting it also own embedding and vector search would have been less code,
but it would have hidden exactly the parts of RAG I need to reason about: which model
embedded what, what is stored in Qdrant, and how search is called. Keeping those explicit
made the pipeline testable with an in-memory store and fakes, and keeps the architecture
legible."

## Gotchas worth mentioning

- `SentenceSplitter` measures chunk size in *tokens* using tiktoken by default (downloads a
  vocabulary on first use); we pass a cheap offline tokenizer.
- Its default sentence tokenizer is NLTK, which needs data files; we pass a regex sentence
  splitter instead (this also sidesteps NLTK 3.10 refusing hard-linked files in
  `uv`-managed virtualenvs).
- Scanned PDFs have no text layer; the loader drops empty pages and ingestion reports
  "No extractable text" rather than indexing nothing silently.
