"""Compatibility shim for backend.app -> backend.server."""

from backend.server import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000)
