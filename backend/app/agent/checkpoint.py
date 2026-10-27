"""Durable LangGraph checkpointer.

``InMemorySaver`` is enough for a single request, but a pending ``save_note`` interrupt
lives on the checkpointer. If the process dies before the human decides, an in-memory
saver has nothing to resume. SQLite under ``data/`` is the local durable analogue of a
Postgres saver; the file is gitignored with the rest of ``data/``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


@asynccontextmanager
async def sqlite_checkpointer(path: Path) -> AsyncIterator[AsyncSqliteSaver]:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        yield saver
