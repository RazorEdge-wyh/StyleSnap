"""启动脚本 / Startup script.

用法 / Usage:
    python run.py
"""
import uvicorn

from backend import config

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=config.PORT, reload=True)
