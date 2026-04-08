"""
Software Factory - FastAPI Server
API REST y WebSocket para conectar con frontend React
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.db import db_manager
from core.logger import get_logger
from fastapi.security import OAuth2PasswordBearer

from routers import auth_router, agents_router, internal_router, sessions_router, analytics_router
from routers import extra_router, skills_router, hq_router, playbook_router, memory_router, claw3d_router, schedules_router, context_router, recon_router

logger = get_logger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# ===========================================
# FastAPI App & Endpoints
# ===========================================

from core.agenda_engine import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_manager.connect()
    start_scheduler()
    logger.info("TripKode Agents API con MongoDB iniciada. Scheduler activo.")
    yield
    await db_manager.disconnect()

app = FastAPI(title="TripKode Agents API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AUTH ENDPOINTS ---

app.include_router(auth_router)

# --- AGENT ENDPOINTS ---

app.include_router(agents_router)
app.include_router(internal_router)

# --- SESSION ENDPOINTS ---

app.include_router(sessions_router)

# --- ANALYTICS ENDPOINTS ---

app.include_router(analytics_router)

# --- EXTRA ENDPOINTS ---

app.include_router(extra_router)
app.include_router(skills_router)
app.include_router(hq_router)
app.include_router(playbook_router)
app.include_router(memory_router)

# --- CLAW3D ENDPOINTS ---

app.include_router(claw3d_router)
app.include_router(schedules_router)
app.include_router(context_router)
app.include_router(recon_router)

# ===========================================
# EJECUCIÓN
# ===========================================

if __name__ == "__main__":
    import uvicorn
    
    print("""
╔══════════════════════════════════════════════════════════╗
║             TripKode Agents API - Iniciando              ║
╠══════════════════════════════════════════════════════════╣
║  Endpoints:                                              ║
║  • POST /api/generate    - Iniciar pipeline              ║
║  • GET  /api/status/{id} - Estado del pipeline            ║
║  • GET  /api/sessions   - Listar sesiones                ║
║  • WS   /ws/{session_id} - WebSocket para updates        ║
║  • GET  /health          - Health check                  ║
╠══════════════════════════════════════════════════════════╣
║  Ejemplo de uso:                                         ║
║  curl -X POST http://localhost:8000/api/generate \\       ║
║    -H "Content-Type: application/json" \\                ║
║    -d '{"prompt": "Crea una API REST para tareas"}'      ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
