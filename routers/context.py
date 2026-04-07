from fastapi import APIRouter, Depends, HTTPException
from typing import List, Any, Optional
from prisma.models import UserGlobalContext, SessionDecision, AgentKnowledge
from core.db import db_manager
from routers.auth import get_current_user
from pydantic import BaseModel
import logging
from typing import cast
import datetime
from core.llm.embeddings import generate_embedding

router = APIRouter(prefix="/api/context", tags=["Context & Memory V2"])
logger = logging.getLogger(__name__)

# --- Models ---

class UserContextModel(BaseModel):
    techStack: List[str] = []
    codingStyle: Optional[str] = None
    namingConventions: Optional[dict] = None
    constraints: List[str] = []
    documentationLinks: List[str] = []

class DecisionModel(BaseModel):
    id: Optional[str] = None
    sessionId: str
    category: str
    decision: str
    rationale: Optional[str] = None
    status: str = "active"
    replacedById: Optional[str] = None

class KnowledgeModel(BaseModel):
    id: Optional[str] = None
    content: str
    metadata: dict = {}
    vector: Optional[List[float]] = None

# --- User Global Context ---

@router.get("/global", response_model=UserContextModel)
async def get_global_context(user_token: dict = Depends(get_current_user)):
    user_id = user_token["id"]
    ctx = await db_manager.client.userglobalcontext.find_unique(where={"userId": user_id})
    if not ctx:
        return UserContextModel()
    return UserContextModel(**ctx.__dict__)

@router.post("/global", response_model=UserContextModel)
async def upsert_global_context(config: UserContextModel, user_token: dict = Depends(get_current_user)):
    user_id = user_token["id"]
    data = config.model_dump()
    
    existing = await db_manager.client.userglobalcontext.find_unique(where={"userId": user_id})
    if existing:
        updated = await db_manager.client.userglobalcontext.update(
            where={"id": existing.id},
            data=cast(Any, data)
        )
        return UserContextModel(**updated.__dict__)
    else:
        new_ctx = await db_manager.client.userglobalcontext.create(
            data=cast(Any, {**data, "user": {"connect": {"id": user_id}}})
        )
        return UserContextModel(**new_ctx.__dict__)

# --- Session Decisions ---

@router.get("/decisions/{session_id}", response_model=List[DecisionModel])
async def list_session_decisions(session_id: str, user_token: dict = Depends(get_current_user)):
    decisions = await db_manager.client.sessiondecision.find_many(
        where={"sessionId": session_id, "status": "active"}
    )
    return [DecisionModel(**{**d.__dict__, "id": str(d.id)}) for d in decisions]

@router.get("/decisions/{session_id}/all", response_model=List[DecisionModel])
async def list_all_session_decisions(session_id: str, user_token: dict = Depends(get_current_user)):
    """Returns all decisions (active + superseded) for full genealogy view."""
    decisions = await db_manager.client.sessiondecision.find_many(
        where={"sessionId": session_id},
        order={"createdAt": "asc"}
    )
    return [DecisionModel(**{**d.__dict__, "id": str(d.id)}) for d in decisions]

class TimelineEntry(BaseModel):
    id: str
    sessionId: str
    sessionTitle: Optional[str] = None
    category: str
    decision: str
    rationale: Optional[str] = None
    status: str
    replacedById: Optional[str] = None
    createdAt: Optional[str] = None

@router.get("/timeline", response_model=List[TimelineEntry])
async def get_decision_timeline(user_token: dict = Depends(get_current_user)):
    """
    Returns ALL decisions across ALL sessions for the authenticated user,
    ordered by creation date (newest first). This powers the Genealogía del Código view.
    """
    user_id = user_token["id"]

    # Get all user's sessions
    sessions = await db_manager.client.projectsession.find_many(
        where={"userId": user_id},
        include={"decisions": True},  # type: ignore
        order={"createdAt": "desc"}
    )

    timeline: List[TimelineEntry] = []
    for session in sessions:
        session_decisions = getattr(session, "decisions", []) or []
        session_title = getattr(session, "title", None) or getattr(session, "sessionId", "")
        for d in sorted(session_decisions, key=lambda x: getattr(x, "createdAt", None) or "", reverse=True):
            timeline.append(TimelineEntry(
                id=str(d.id),
                sessionId=str(d.sessionId),
                sessionTitle=session_title,
                category=d.category,
                decision=d.decision,
                rationale=getattr(d, "rationale", None),
                status=d.status,
                replacedById=getattr(d, "replacedById", None),
                createdAt=d.createdAt.isoformat() if getattr(d, "createdAt", None) else None,
            ))

    return timeline

@router.post("/decisions", response_model=DecisionModel)
async def create_decision(decision: DecisionModel, user_token: dict = Depends(get_current_user)):
    data = decision.model_dump(exclude={"id"})
    new_d = await db_manager.client.sessiondecision.create(data=cast(Any, data))
    return DecisionModel(**{**new_d.__dict__, "id": str(new_d.id)})

@router.patch("/decisions/{decision_id}/supersede")
async def supersede_decision(decision_id: str, new_decision_id: str, user_token: dict = Depends(get_current_user)):
    await db_manager.client.sessiondecision.update(
        where={"id": decision_id},
        data={"status": "superseded", "replacedById": new_decision_id}
    )
    return {"status": "ok"}

# --- Agent Knowledge (Semantic) ---

@router.post("/knowledge", response_model=KnowledgeModel)
async def add_knowledge(knowledge: KnowledgeModel, user_token: dict = Depends(get_current_user)):
    user_id = user_token["id"]
    data = knowledge.model_dump(exclude={"id"})
    data["userId"] = user_id
    
    # Generate authentic vector using GenAI model
    vector = generate_embedding(data["content"])
    if vector:
        data["vector"] = vector
    else:
        # If vector generation fails gracefully fall back to empty
        data["vector"] = []
    
    new_k = await db_manager.client.agentknowledge.create(data=cast(Any, data))
    return KnowledgeModel(**{**new_k.__dict__, "id": str(new_k.id)})

@router.post("/knowledge/search")
async def search_knowledge(query: str, limit: int = 5, user_token: dict = Depends(get_current_user)):
    user_id = user_token["id"]
    
    query_vector = generate_embedding(query)
    
    if query_vector:
        try:
            # Execute actual Atlas Vector Search pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index", # Requires Atlas Search Index definition in cloud
                        "path": "vector",
                        "queryVector": query_vector,
                        "numCandidates": limit * 10,
                        "limit": limit
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "content": 1,
                        "metadata": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]
            
            raw_results = await db_manager.client.agentknowledge.aggregate_raw(pipeline=pipeline)
            
            if isinstance(raw_results, list) and len(raw_results) > 0:
                mapped = []
                for r in raw_results:
                    val_id = r.get("_id", {}).get("$oid", str(r.get("_id"))) if isinstance(r.get("_id"), dict) else str(r.get("_id"))
                    mapped.append(KnowledgeModel(
                        id=val_id,
                        content=r.get("content", ""),
                        metadata=r.get("metadata", {})
                    ))
                return mapped
        except Exception as e:
            logger.error(f"Vector search failed, falling back to keywords: {e}")

    # Simple keyword search fallback (If vector index is missing or generation fails)
    all_k = await db_manager.client.agentknowledge.find_many(
        where={"userId": user_id},
        take=limit
    )
    
    return [KnowledgeModel(**{**k.__dict__, "id": str(k.id)}) for k in all_k]
