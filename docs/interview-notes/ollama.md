# Ollama

## What it is

Ollama is a local LLM runtime. It downloads open-weight models (Qwen, Llama, Mistral,
gpt-oss, embedding models such as `nomic-embed-text`) in a quantised GGUF format, runs
them on CPU or GPU via llama.cpp, and exposes them over a simple HTTP API on
`http://localhost:11434`. It also offers an OpenAI-compatible endpoint, so most SDKs that
speak to OpenAI can be pointed at it unchanged.

## Why we use it

- Free and fully local: no API keys, no per-token cost, documents never leave the machine.
- One server for both the chat model (`qwen2.5:14b`) and the embedding model
  (`nomic-embed-text`), which keeps configuration to a single URL.
- Native tool calling and JSON/structured output for supported models, which Phases 4-5
  rely on.

## What problem it solves

Running a modern LLM by hand means managing weights, quantisation, GPU memory and a
serving loop. Ollama turns that into `ollama pull <model>` and an HTTP call, while still
letting you choose the model per request.

## Alternatives

| Option | Trade-off |
| --- | --- |
| vLLM / TGI | Higher throughput for multi-user serving; heavier setup, Linux + GPU focused |
| llama.cpp server / LM Studio | Similar local story; Ollama has the broader library and tooling |
| Hosted APIs (OpenAI, Azure OpenAI, Anthropic) | Stronger frontier models, zero ops; cost, data leaves the machine, vendor lock-in |

## How it is wired in this project

- `app/llm/base.py` defines `LLMProvider` (a `Protocol` with `chat()` and `health()`).
- `app/llm/ollama.py` implements it with LangChain's `ChatOllama` as the HTTP client, and
  checks `GET /api/tags` to confirm the configured model is pulled.
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL` come from the environment (`app/config.py`).
- When the backend runs in Docker the URL becomes
  `http://host.docker.internal:11434` so the container can reach Ollama on the host.

## How I would explain it in an interview

"Ollama is the inference layer. I treat it like any other model endpoint behind a small
`LLMProvider` interface, so the application code does not care whether tokens come from a
local 14B model or a hosted API. Locally that gives me zero cost and full data privacy;
in production I would swap the provider for a managed service and keep everything above
it unchanged. The provider also reports latency and token usage so the observability
layer can track cost and performance per request."

## Gotchas worth mentioning

- First request after idle is slow because the model loads into memory; `keep_alive`
  controls how long it stays resident.
- Smaller models (3B) are fast but unreliable at tool calling; 7B-14B is the practical
  floor for agent workflows.
- Context window (`num_ctx`) defaults are modest; RAG prompts should budget tokens.
