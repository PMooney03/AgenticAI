# CI/CD (GitHub Actions)

## What it is

CI (continuous integration) runs the same checks on every push and pull request that a
developer runs locally: lint, unit tests, the golden-set eval, a frontend production
build, and a Docker image build. CD (continuous delivery) would then push those images
and deploy; this project stops at "the images build". There is no registry and no cloud
account.

## Why we use it

- The golden set exists so a prompt or routing change cannot merge on vibes. CI is where
  that gate actually lives.
- Building the image on Ubuntu catches "works in my Windows venv" bugs (path separators,
  pywin32, forgotten lockfile updates).
- Interviewers expect to see a workflow file, not a claim that "I would add CI later".

## What problem it solves

Silent breakage. Ruff, pytest, Vitest and `python -m app.eval` are fast and need no
Ollama. If they pass, the agent graph, MCP tools, HITL interrupt and quality scores still
behave. The image build proves the Dockerfiles stay installable from the lockfiles.

## Alternatives

| Option | Trade-off |
| --- | --- |
| GitHub Actions (chosen) | Free for public/small private repos; YAML in the repo |
| Azure DevOps pipelines | Natural if the company is already on Azure; extra product |
| GitLab CI | Same idea, different host |
| Only local pre-commit | Fast; does not run on a clean machine |

## How it is wired in this project

`.github/workflows/ci.yml`:

1. **backend** — `uv sync --frozen`, `ruff check` + `format --check`, `pytest`,
   `python -m app.eval`.
2. **frontend** — `npm ci`, oxlint, Vitest, `npm run build`.
3. **docker** — after the two test jobs: `docker compose config --profile app` and
   `docker compose --profile app build`. Images are not pushed.

Concurrency cancels a stale run on the same branch. `permissions: contents: read` is
the least privilege the jobs need.

## How I would explain it in an interview

"CI is the contract. The backend job is the LLMOps gate: unit tests plus a deterministic
eval, no GPU. The frontend job is lint, tests and a production build so TypeScript errors
cannot hide behind Vite HMR. The docker job is the packaging gate: if `uv.lock` or
`package-lock.json` drifted, the image fails here instead of on a teammate's laptop.
I am not doing CD because there is no environment to deploy to; the next step would be
push to ACR and roll a Container App."

## Gotchas worth mentioning

- `--frozen` / `npm ci` fail closed when the lockfile is stale. That is the point.
- Do not run the live 14b model in CI. It is slow, non-deterministic and needs weights.
- `pull_request` from a fork may not have secrets; this workflow needs none.
- Image *build* is not an image *run*. A compose `up` smoke test would need Ollama or a
  fake-provider mode; that is a reasonable follow-up, not required to prove packaging.
