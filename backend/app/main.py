from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.agent_routes import router as agent_router

app = FastAPI(
    title="AI Multi-Level Agent System",
    description="A multi-agent orchestrator that processes business leads and recommends the next best action.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router, prefix="/api")


@app.get("/")
def root():
    return {
        "service": "AI Multi-Level Agent System",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}
