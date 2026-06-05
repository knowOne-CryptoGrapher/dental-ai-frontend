from fastapi import APIRouter, HTTPException, Depends, Response
from datetime import datetime, timezone
import logging
import uuid

from auth import get_db, get_current_user
from dependencies import require_feature
from models import KnowledgeDocument, KnowledgeDocumentCreate, KnowledgeDocumentUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["knowledge"])


@router.get("/knowledge")
async def list_knowledge(
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("knowledge_base")),
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return []
    docs = await db.knowledge.find(
        {"practice_id": practice_id}, {"_id": 0}
    ).sort("updated_at", -1).to_list(1000)
    return docs


@router.post("/knowledge", status_code=201)
async def create_knowledge(
    body: KnowledgeDocumentCreate,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("knowledge_base")),
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        raise HTTPException(status_code=403, detail="No practice context")

    now = datetime.now(timezone.utc)
    doc = KnowledgeDocument(
        id=str(uuid.uuid4()),
        practice_id=practice_id,
        title=body.title,
        content=body.content,
        category=body.category,
        created_at=now,
        updated_at=now,
        created_by=current_user.get("id", ""),
    )
    doc_dict = doc.model_dump()
    await db.knowledge.insert_one({**doc_dict})
    return doc_dict


@router.put("/knowledge/{doc_id}")
async def update_knowledge(
    doc_id: str,
    body: KnowledgeDocumentUpdate,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("knowledge_base")),
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    existing = await db.knowledge.find_one(
        {"id": doc_id, "practice_id": practice_id}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.knowledge.update_one({"id": doc_id}, {"$set": updates})

    updated = await db.knowledge.find_one({"id": doc_id}, {"_id": 0})
    return updated


@router.delete("/knowledge/{doc_id}", status_code=204)
async def delete_knowledge(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("knowledge_base")),
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    result = await db.knowledge.delete_one(
        {"id": doc_id, "practice_id": practice_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=204)
