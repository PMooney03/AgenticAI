"""Make pywin32 importable in uvicorn workers.

The official MCP SDK pulls ``mcp.server.stdio`` even for in-memory ``Client(server)``.
On Windows that module does ``import pywintypes``. The DLL lives in
``site-packages/pywin32_system32`` and is not always on the search path in a spawned
uvicorn worker, especially when the first import happens in FastAPI's dependency
threadpool.

This helper is idempotent and a no-op on non-Windows.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_pywin32() -> None:
    if sys.platform != "win32":
        return
    site = Path(sys.prefix) / "Lib" / "site-packages"
    dll_dir = site / "pywin32_system32"
    extras = (dll_dir, site / "win32", site / "win32" / "lib")
    for folder in extras:
        if not folder.is_dir():
            continue
        path = str(folder)
        if path not in sys.path:
            sys.path.insert(0, path)
    if dll_dir.is_dir():
        os.add_dll_directory(str(dll_dir))
        os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")
