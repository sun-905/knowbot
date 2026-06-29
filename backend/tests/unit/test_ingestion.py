"""知识库入库服务单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from app.services.ingestion import create_document, ALLOWED_TYPES, MAX_FILE_SIZE


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_creates_with_processing_status(self, tmp_path):
        """创建文档时状态为 processing"""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.commit = AsyncMock()

        with patch("app.services.ingestion.TEMP_DIR", tmp_path):
            doc, temp_path = await create_document(
                db, kb_id=1, filename="test.txt",
                content=b"hello world", mime_type="text/plain"
            )
            assert doc.status == "processing"
            assert doc.filename == "test.txt"
            assert doc.file_type == "txt"
            assert doc.chunk_count == 0
            assert temp_path.exists()

    @pytest.mark.asyncio
    async def test_rejects_invalid_type(self):
        db = AsyncMock()
        with pytest.raises(ValueError, match="不支持的文件类型"):
            await create_document(db, 1, "test.jpg", b"data", "image/jpeg")

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self):
        db = AsyncMock()
        big_data = b"x" * (MAX_FILE_SIZE + 1)
        with pytest.raises(ValueError, match="文件过大"):
            await create_document(db, 1, "big.txt", big_data, "text/plain")

    @pytest.mark.asyncio
    async def test_commits_before_return(self, tmp_path):
        """返回前必须 commit，确保 BackgroundTasks 能读到记录"""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.commit = AsyncMock()

        with patch("app.services.ingestion.TEMP_DIR", tmp_path):
            await create_document(db, 1, "test.md", b"# Hello", "text/markdown")
            db.commit.assert_called_once()


class TestAllowedTypes:
    def test_pdf_allowed(self):
        assert "application/pdf" in ALLOWED_TYPES

    def test_txt_allowed(self):
        assert "text/plain" in ALLOWED_TYPES

    def test_md_allowed(self):
        assert "text/markdown" in ALLOWED_TYPES

    def test_word_not_allowed(self):
        assert "application/msword" not in ALLOWED_TYPES
