from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy import select, func

CST = timezone(timedelta(hours=8))


def _iso(dt: datetime | None) -> str:
    """将 datetime 转为带北京时区的 ISO 字符串，前端才能正确换算"""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return dt.isoformat()
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..middleware.auth import get_current_user, require_admin
from ..models.knowledge_doc import KnowledgeDoc
from ..models.knowledge_base import KnowledgeBase
from ..models.user import User
from ..services.ingestion import create_document, process_document, delete_document

router = APIRouter(prefix="/knowledge", tags=["知识库"])


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: str
    is_default: bool

    model_config = {"from_attributes": True}


class KnowledgeDocResponse(BaseModel):
    id: int
    kb_id: int
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    error_msg: str | None
    created_at: str

    model_config = {"from_attributes": True}


class PaginatedDocs(BaseModel):
    items: list[KnowledgeDocResponse]
    total: int
    page: int
    page_size: int


class CreateBaseRequest(BaseModel):
    name: str
    description: str = ""


@router.get("/bases", response_model=list[KnowledgeBaseResponse])
async def list_bases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.id))
    return result.scalars().all()


@router.post("/bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_base(
    req: CreateBaseRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    kb = KnowledgeBase(name=req.name, description=req.description)
    db.add(kb)
    await db.flush()
    await db.refresh(kb)
    await db.commit()
    return kb


@router.delete("/bases/{base_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_base(
    base_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == base_id))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    if kb.is_default:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除默认知识库")
    # 删除该知识库下的所有文档
    docs_result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.kb_id == base_id))
    for doc in docs_result.scalars().all():
        await delete_document(db, doc)
    await db.delete(kb)
    await db.commit()


@router.post("/docs/upload", response_model=KnowledgeDocResponse, status_code=status.HTTP_201_CREATED)
async def upload_doc(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    kb_id: int = Form(default=1),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名为空")

    try:
        content = await file.read()
        doc, temp_path = await create_document(
            db=db,
            kb_id=kb_id,
            filename=file.filename,
            content=content,
            mime_type=file.content_type or "application/octet-stream",
        )
        # 后台异步处理文档
        background_tasks.add_task(process_document, doc.id, temp_path)

        return {
            "id": doc.id,
            "kb_id": doc.kb_id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "chunk_count": doc.chunk_count,
            "status": doc.status,
            "error_msg": doc.error_msg,
            "created_at": _iso(doc.created_at),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/docs", response_model=PaginatedDocs)
async def list_docs(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc()).offset(offset).limit(page_size)
    )
    docs = result.scalars().all()

    total_result = await db.execute(select(func.count(KnowledgeDoc.id)))
    total = total_result.scalar()

    return {
        "items": [
            {
                "id": d.id, "kb_id": d.kb_id, "filename": d.filename,
                "file_type": d.file_type, "file_size": d.file_size,
                "chunk_count": d.chunk_count, "status": d.status,
                "error_msg": d.error_msg,
                "created_at": _iso(d.created_at),
            }
            for d in docs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/docs/{doc_id}", response_model=KnowledgeDocResponse)
async def get_doc(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return {
        "id": doc.id, "kb_id": doc.kb_id, "filename": doc.filename,
        "file_type": doc.file_type, "file_size": doc.file_size,
        "chunk_count": doc.chunk_count, "status": doc.status,
        "error_msg": doc.error_msg,
        "created_at": _iso(doc.created_at),
    }


@router.delete("/docs/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_doc(
    doc_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    await delete_document(db, doc)
