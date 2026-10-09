"""Atalho para rodar o jogo: python run.py  (abre em http://127.0.0.1:8000)"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv é opcional
    pass

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.main:app", host=os.getenv("HOST", "127.0.0.1"), port=port)
