"""本地启动脚本：python run.py 后访问 http://127.0.0.1:8000 。"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = os.getenv("RELOAD", "0") in {"1", "true", "True"}
    print(f"职称评审科研积分系统启动中... 请访问 http://{host}:{port}")
    print(f"接口文档: http://{host}:{port}/docs")
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload_enabled)
