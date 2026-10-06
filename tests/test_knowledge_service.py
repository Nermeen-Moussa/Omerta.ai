"""Phase 12 - knowledge service integration tests (real omerta_test DB)."""

import pytest
from domain.errors import NotFoundError, ValidationError
from domain.services.knowledge_service import CORPUS_VERSION, KnowledgeService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_ingest_is_idempotent(test_engine) -> None:
    # The seed already ingested the corpus; re-ingestion must upsert cleanly
    # (no inserts, no duplicates) and keep the index stable.
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        first = await KnowledgeService(session).ingest_corpus()
        await session.commit()
        second = await KnowledgeService(session).ingest_corpus()
        await session.commit()
    assert first.documents_seen == 4
    assert first.documents_inserted == 0  # already present from seed
    assert first.documents_updated == 4  # upsert path
    assert first.chunks_inserted == 0
    assert second.documents_inserted == 0
    assert second.chunks_inserted == 0
    assert second.chunks_updated == 0
    assert second.index_terms == first.index_terms


@pytest.mark.asyncio
async def test_search_surfaces_shared_device_guidance(
    knowledge_session: AsyncSession,
) -> None:
    result = await KnowledgeService(knowledge_session).search("shared device fraud ring", top_k=3)
    assert result.count >= 1
    top = result.results[0]
    # One of the two shared-infrastructure documents must lead the ranking.
    assert top.document_id in {"DOC-FATF-TYPOLOGIES", "DOC-SHARED-DEVICE-POLICY"}
    assert top.score > 0
    assert "shared" in top.content.lower()


@pytest.mark.asyncio
async def test_search_empty_for_gibberish_query(knowledge_session: AsyncSession) -> None:
    result = await KnowledgeService(knowledge_session).search("zzzqqqxyzzy gibberishonlytoken")
    assert result.count == 0
    assert result.results == []


@pytest.mark.asyncio
async def test_search_deterministic_ranking(knowledge_session: AsyncSession) -> None:
    first = await KnowledgeService(knowledge_session).search("mule", top_k=10)
    again = await KnowledgeService(knowledge_session).search("mule", top_k=10)
    assert [c.chunk_id for c in first.results] == [c.chunk_id for c in again.results]


@pytest.mark.asyncio
async def test_get_document_not_found(knowledge_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError) as excinfo:
        await KnowledgeService(knowledge_session).get_document("DOC-MISSING")
    assert excinfo.value.payload["resource"] == "knowledge_document"


@pytest.mark.asyncio
async def test_get_document_section_case_insensitive_single_match(
    knowledge_session: AsyncSession,
) -> None:
    result = await KnowledgeService(knowledge_session).get_document_section(
        "DOC-FATF-TYPOLOGIES", "mule accounts"
    )
    assert result.section == "Mule Accounts"


@pytest.mark.asyncio
async def test_get_document_section_blank_rejected(
    knowledge_session: AsyncSession,
) -> None:
    with pytest.raises(ValidationError):
        await KnowledgeService(knowledge_session).get_document_section("DOC-FATF-TYPOLOGIES", "   ")


@pytest.mark.asyncio
async def test_corpus_stats_shape(knowledge_session: AsyncSession) -> None:
    stats = await KnowledgeService(knowledge_session).corpus_stats()
    assert stats["documents"] == 4
    assert stats["chunks"] == 12
    assert stats["index_terms"] > 0
    assert stats["corpus_version"] == CORPUS_VERSION
    assert stats["index_version"] == "tfidf-v1"
