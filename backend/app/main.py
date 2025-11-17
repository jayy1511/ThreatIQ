from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, analyze, stats, chat

app = FastAPI(title="ThreatIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      
    allow_credentials=False,  
    allow_methods=["*"],      
    allow_headers=["*"],      
)

# -------------- ROUTERS --------------

app.include_router(auth.router, prefix="/auth")

app.include_router(analyze.router)

app.include_router(stats.router)

app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}
