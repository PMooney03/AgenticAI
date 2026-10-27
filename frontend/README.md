# Agentic Second Brain — frontend

React + TypeScript + Vite UI for the local RAG backend.

```powershell
copy .env.example .env   # optional; default API is http://localhost:8000
npm install
npm run dev              # http://localhost:5173
npm test
npm run lint
npm run build
```

If the backend is not on port 8000, set `VITE_API_BASE_URL` (for example `http://localhost:8010`).
The backend must list this origin in `CORS_ORIGINS`.

See the root [README](../README.md) for the full project.
