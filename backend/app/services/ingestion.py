import os
import uuid
from pathlib import Path

import fitz  # PyMuPDF，PDF 文本提取 + 页面渲染
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import async_session
from ..core.embedding import encode
from ..core.qdrant_client import COLLECTION_NAME, get_qdrant
from ..models.knowledge_doc import KnowledgeDoc
from .retrieval import add_to_bm25, remove_from_bm25, rebuild_bm25

ALLOWED_TYPES = {"application/pdf": "pdf", "text/plain": "txt", "text/markdown": "md"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
TEMP_DIR = Path("tmp_uploads")


def _extract_text_with_pymupdf(file_path: Path) -> str | None:
    """用 PyMuPDF 提取文本，处理 SimpleDirectoryReader 无法解析的 PDF。
    返回提取到的文本；如果没有提取到任何文本，返回 None 以便升级到 OCR。
    """
    try:
        doc = fitz.open(str(file_path))
        texts = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                texts.append(text.strip())
        doc.close()
        if texts:
            return "\n\n".join(texts)
    except Exception as e:
        logger.warning(f"PyMuPDF 文本提取失败: {e}")
    return None


def _ocr_pdf(file_path: Path) -> str | None:
    """OCR 回退：将 PDF 每页渲染为图片后用 PaddleOCR + PP-Structure 识别。
    处理扫描件 / 图片型 PDF，是最重的一级回退。

    PP-Structure 能识别表格并输出 Markdown 格式，保留表格结构。
    非表格区域回退到标准 OCR 逐行识别。
    返回识别到的全部文本（含 Markdown 表格）；失败返回 None。
    """
    try:
        from paddleocr import PaddleOCR, PPStructureV3
    except ImportError:
        logger.error("PaddleOCR 未安装，无法执行 OCR。请运行: pip install paddlepaddle paddleocr")
        return None

    try:
        ocr = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
        structure_engine = PPStructureV3(
            lang="ch",
            use_table_recognition=True,
            use_region_detection=True,
        )
        doc = fitz.open(str(file_path))
        page_texts = []
        table_count = 0

        for page_num, page in enumerate(doc):
            try:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")

                # 先用 PP-Structure 做版面分析，识别表格+文本区域
                structure_result = structure_engine(img_bytes)
                page_parts = []

                if structure_result:
                    for region in structure_result:
                        region_type = region.get("type", "")
                        if region_type == "table":
                            # 表格 → Markdown 格式，保留结构化信息
                            md_table = _render_table_markdown(region.get("res", {}))
                            if md_table:
                                page_parts.append(md_table)
                                table_count += 1
                        elif region_type == "figure":
                            # 图片区域：尝试 OCR 提取其中文字
                            pass  # 图片中的文字通常被 text 区域覆盖，跳过
                        else:
                            # 文本区域：直接取 PP-Structure 的文本
                            text = _extract_region_text(region)
                            if text.strip():
                                page_parts.append(text.strip())
                else:
                    # PP-Structure 无结果，回退到标准 OCR
                    ocr_result = ocr.ocr(img_bytes, cls=True)
                    if ocr_result and ocr_result[0]:
                        page_text = "\n".join(
                            line[1][0] for line in ocr_result[0]
                            if line and len(line) > 1
                        )
                        if page_text.strip():
                            page_parts.append(page_text.strip())

                if page_parts:
                    page_texts.append("\n\n".join(page_parts))

            except Exception as e:
                logger.warning(f"OCR 第 {page_num + 1} 页失败: {e}")

        doc.close()

        if page_texts:
            logger.info(
                f"OCR 完成，共识别 {len(page_texts)} 页文本"
                + (f"，含 {table_count} 个表格" if table_count else "")
            )
            return "\n\n---\n\n".join(page_texts)
    except Exception as e:
        logger.error(f"OCR 处理失败: {e}")
    return None


def _render_table_markdown(table_data: dict) -> str:
    """将 PP-Structure 表格数据渲染为 Markdown 表格"""
    cells = table_data.get("cells", [])
    if not cells:
        return ""

    # PP-Structure 返回的 cells 是 [row][col] 的二维结构，每个 cell 含 text 和 bbox
    # 先找最大行列数
    max_row = 0
    max_col = 0
    cell_map: dict[tuple[int, int], str] = {}

    for cell in cells:
        # 尝试多种 key 格式
        if isinstance(cell, dict):
            row = cell.get("row", cell.get("rowspan", 0))
            col = cell.get("col", cell.get("colspan", 0))
            text = cell.get("text", cell.get("content", ""))
        elif isinstance(cell, (list, tuple)) and len(cell) >= 3:
            # PaddleOCR 旧格式: [row, col, text]
            row, col, text = cell[0], cell[1], str(cell[2]) if len(cell) > 2 else ""
        else:
            continue
        row, col = int(row), int(col)
        cell_map[(row, col)] = str(text).replace("\n", " ").replace("|", "\\|")
        max_row = max(max_row, row)
        max_col = max(max_col, col)

    if max_row == 0 and max_col == 0:
        return ""

    # 渲染为 Markdown 表格
    lines = []
    for r in range(max_row + 1):
        row_cells = [cell_map.get((r, c), "") for c in range(max_col + 1)]
        lines.append("| " + " | ".join(row_cells) + " |")
        if r == 0:
            # 表头分隔线
            lines.append("| " + " | ".join(["---"] * (max_col + 1)) + " |")

    return "\n".join(lines)


def _extract_region_text(region: dict) -> str:
    """从 PP-Structure 的文本区域提取文字"""
    res = region.get("res", {})
    if isinstance(res, str):
        return res
    if isinstance(res, dict):
        # 可能是嵌套的文本块
        text = res.get("text", res.get("content", ""))
        if isinstance(text, str):
            return text
        # 也可能是段落列表
        blocks = res.get("blocks", res.get("text_blocks", []))
        if blocks:
            return "\n".join(
                b.get("text", b.get("content", "")) if isinstance(b, dict) else str(b)
                for b in blocks
            )
    if isinstance(res, list):
        return "\n".join(
            item.get("text", item.get("content", "")) if isinstance(item, dict) else str(item)
            for item in res
        )
    return str(res) if res else ""


async def create_document(
    db: AsyncSession,
    kb_id: int,
    filename: str,
    content: bytes,
    mime_type: str,
) -> tuple[KnowledgeDoc, Path]:
    """仅创建文档记录并落盘临时文件，状态设为 processing，立即返回"""
    if mime_type not in ALLOWED_TYPES:
        raise ValueError(f"不支持的文件类型: {mime_type}，仅支持 PDF/TXT/Markdown")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"文件过大: {len(content)} bytes，上限 {MAX_FILE_SIZE} bytes")

    file_type = ALLOWED_TYPES[mime_type]
    TEMP_DIR.mkdir(exist_ok=True)
    temp_path = TEMP_DIR / f"{uuid.uuid4().hex}_{filename}"
    temp_path.write_bytes(content)

    doc = KnowledgeDoc(
        kb_id=kb_id,
        filename=filename,
        file_type=file_type,
        file_size=len(content),
        chunk_count=0,
        status="processing",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    # 必须在返回前提交，因为 BackgroundTasks 在 get_db() 提交之前执行
    await db.commit()

    logger.info(f"文档 '{filename}' (id={doc.id}) 已创建，等待后台处理")
    return doc, temp_path


async def process_document(doc_id: int, temp_path: Path):
    """后台处理文档：解析 → 切片 → 向量化 → 写入 Qdrant + BM25 → 更新状态"""
    async with async_session() as db:
        try:
            result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
            doc = result.scalar_one_or_none()
            if not doc:
                logger.error(f"文档 id={doc_id} 不存在，取消后台处理")
                return

            # 解析文档 —— 三级回退策略
            # L1: SimpleDirectoryReader（文本型 PDF / TXT / MD）
            # L2: PyMuPDF 原生文本提取（结构复杂但仍含文字层的 PDF）
            # L3: PaddleOCR（扫描件 / 图片型 PDF）
            raw_text = ""
            parse_method = ""

            if temp_path.suffix.lower() == ".pdf":
                # PDF：走三级回退
                reader = SimpleDirectoryReader(input_files=[str(temp_path)])
                docs = reader.load_data()
                if docs and any(d.text.strip() for d in docs):
                    raw_text = "\n\n".join(d.text for d in docs if d.text.strip())
                    parse_method = "SimpleDirectoryReader"
                else:
                    logger.info(f"SimpleDirectoryReader 未提取到文本，尝试 PyMuPDF: {doc.filename}")
                    raw_text = _extract_text_with_pymupdf(temp_path) or ""
                    if raw_text.strip():
                        parse_method = "PyMuPDF"
                    else:
                        logger.info(f"PyMuPDF 未提取到文本，尝试 OCR（可能需要 10-30 秒）: {doc.filename}")
                        raw_text = _ocr_pdf(temp_path) or ""
                        if raw_text.strip():
                            parse_method = "PaddleOCR"
                        else:
                            raise ValueError("三级解析均失败：此 PDF 可能是纯图片且 OCR 不可用，请上传可复制文字的版本")
            else:
                # TXT / MD：直接走 SimpleDirectoryReader
                reader = SimpleDirectoryReader(input_files=[str(temp_path)])
                docs = reader.load_data()
                if not docs or not any(d.text.strip() for d in docs):
                    raise ValueError("文档解析失败：未能提取到文本内容")
                raw_text = "\n\n".join(d.text for d in docs if d.text.strip())
                parse_method = "SimpleDirectoryReader"

            logger.info(f"文档 '{doc.filename}' 解析方式: {parse_method}, 文本长度: {len(raw_text)} 字")

            # 将纯文本包装为 LlamaIndex Document 以便切片器使用
            from llama_index.core import Document as LlamaDocument
            docs = [LlamaDocument(text=raw_text)]

            # 切片
            splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
            nodes = splitter.get_nodes_from_documents(docs)
            if not nodes:
                raise ValueError("文档切片后无内容")

            texts = [node.get_content().strip() for node in nodes]
            texts = [t for t in texts if t]
            if not texts:
                raise ValueError(
                    "文档切片后无有效文本——"
                    "PDF 可能为纯图片且 OCR 失败/未安装，或文档内容为空白"
                )
            chunk_count = len(texts)
            logger.info(f"文档 '{doc.filename}' 解析为 {chunk_count} 个非空切片")

            # 批量向量化
            embeddings = await encode(texts)

            # 批量写入 Qdrant
            qdrant = await get_qdrant()
            points = []
            for i, (text, emb) in enumerate(zip(texts, embeddings)):
                point_id = uuid.uuid4().hex
                points.append({
                    "id": point_id,
                    "vector": emb.tolist(),
                    "payload": {
                        "kb_id": doc.kb_id,
                        "doc_id": doc.id,
                        "doc_name": doc.filename,
                        "chunk_index": i,
                        "text": text[:2000],
                        "char_count": len(text),
                    },
                })

            from qdrant_client.models import PointStruct
            batch_size = 32
            for i in range(0, len(points), batch_size):
                batch = [PointStruct(**p) for p in points[i:i + batch_size]]
                qdrant.upsert(collection_name=COLLECTION_NAME, points=batch)

            # 更新 BM25 索引
            for i, text in enumerate(texts):
                add_to_bm25(f"{doc.id}:{i}", text)

            # 标记为就绪
            doc.status = "ready"
            doc.chunk_count = chunk_count
            await db.commit()
            await db.refresh(doc)

            logger.info(f"文档 '{doc.filename}' (id={doc.id}) 入库完成: {chunk_count} 个切片")

        except Exception as e:
            logger.error(f"文档 id={doc_id} 后台处理失败: {e}")
            try:
                result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = "failed"
                    doc.error_msg = str(e)
                    await db.commit()
            except Exception as inner:
                logger.error(f"更新失败状态时出错: {inner}")
        finally:
            if temp_path.exists():
                temp_path.unlink()


async def delete_document(db: AsyncSession, doc: KnowledgeDoc) -> None:
    """从 Qdrant 和 BM25 中删除文档"""
    qdrant = await get_qdrant()
    from qdrant_client.http import models as qmodels

    qdrant.delete(
        collection_name=COLLECTION_NAME,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="doc_id", match=qmodels.MatchValue(value=doc.id))]
            )
        ),
    )

    # 从 BM25 中移除
    for i in range(doc.chunk_count):
        remove_from_bm25(f"{doc.id}:{i}")

    await db.delete(doc)
    await db.flush()
    logger.info(f"文档 '{doc.filename}' (id={doc.id}) 已删除，{doc.chunk_count} 个切片被移除")


async def process_pending_documents() -> None:
    """启动时扫描并补处理所有 status='processing' 的文档

    覆盖场景：上传后服务器重启，BackgroundTasks 丢失，文档永远卡在 processing。
    有临时文件的就继续处理，没有的标记为 failed。
    """
    async with async_session() as db:
        result = await db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.status == "processing")
        )
        pending = result.scalars().all()

        if not pending:
            return

        logger.info(f"发现 {len(pending)} 个待处理文档，开始补处理")

        for doc in pending:
            # 查找临时文件
            candidates = list(TEMP_DIR.glob(f"*_{doc.filename}"))
            if not candidates:
                logger.warning(f"文档 '{doc.filename}' (id={doc.id}) 临时文件已丢失，标记为失败")
                doc.status = "failed"
                doc.error_msg = "服务器重启后临时文件丢失，无法恢复处理"
                await db.commit()
                continue

            temp_path = candidates[0]
            logger.info(f"补处理文档 '{doc.filename}' (id={doc.id})，临时文件: {temp_path}")
            try:
                await process_document(doc.id, temp_path)
            except Exception as e:
                logger.error(f"补处理文档 id={doc.id} 失败: {e}")


async def rebuild_bm25_from_qdrant() -> None:
    """从 Qdrant 中的全部文档重建 BM25 索引（启动时调用）"""
    qdrant = await get_qdrant()
    from qdrant_client.http import models as qmodels

    rebuild_bm25()
    offset = None
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            if point.payload:
                chunk_index = point.payload.get("chunk_index", 0)
                doc_id = point.payload.get("doc_id", 0)
                key = f"{doc_id}:{chunk_index}"
                text = point.payload.get("text", "")
                add_to_bm25(key, text)
        if next_offset is None:
            break
        offset = next_offset
    logger.info("BM25 索引已从 Qdrant 重建完成")
