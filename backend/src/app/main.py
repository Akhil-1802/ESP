from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .features.drawing_generation.router import router

app = FastAPI(
    title="ESP Generation API",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://railway-esp.netlify.app",
        "https://esp-beige.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Server-Timing", "X-ESP-Cache", "X-ESP-Generation-ID", "Content-Disposition"],
)
app.include_router(router)


@app.get("/health")
@app.head("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
