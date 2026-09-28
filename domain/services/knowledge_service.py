"""Knowledge service (Phase 12): deterministic ingestion + retrieval.

The knowledge layer stores curated policy/regulation/typology documents as
data and answers controlled queries over them. Everything is deterministic:
the same corpus always yields the same chunks, the same vectors, and the same
ranking for a given query. No LLM, no external embedding service, no network.

Provenance: every retrieved chunk carries document id, title, type, section,
jurisdiction, effective date, and version, so any agent finding that cites
knowledge is fully traceable. An empty result is reported as empty - results
are never padded with irrelevant material (no fabricated citations).
"""

import hashlib
import json
import logging
import re
from typing import Any

from infrastructure.database.models import KnowledgeChunk, KnowledgeDocument
from infrastructure.knowledge import embeddings
from infrastructure.knowledge.corpus import KNOWLEDGE_CORPUS
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.errors import NotFoundError, ValidationError
from domain.schemas import (
    KnowledgeChunkOut,
    KnowledgeDocumentOut,
    KnowledgeIngestOut,
    KnowledgeSearchOut,
    KnowledgeSectionOut,
)

logger = logging.getLogger(__name__)

KNOWLEDGE_INDEX_VERSION = "tfidf-v1"
CORPUS_VERSION = "corpus-v1"
MAX_QUERY_LENGTH = 512
DEFAULT_TOP_K = 3
MAX_TOP_K = 10
MIN_SCORE = 0.0  # chunks scoring at or below this are not returned

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_DOC_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")


def _slugify(text: str) -> str:
    """Stable slug for a section name (chunk-id component)."""
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return slug or "section"


def _chunk_hash(document_id: str, section: str, content: str) -> str:
    """SHA-256 over canonical chunk content (corpus-change detection)."""
    canonical = json.dumps(
        {"d": document_id, "s": section, "c": content},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_document_id(document_id: str) -> str:
    """Validate a document id (used in lookups and chunk-id assembly)."""
    cleaned = (document_id or "").strip()
    if not cleaned:
        raise ValidationError("document_id must not be empty", field="document_id")
    if len(cleaned) > 64:
        raise ValidationError("document_id exceeds 64 characters", field="document_id")
    if not _DOC_ID_RE.match(cleaned):
        raise ValidationError("document_id must match [A-Z0-9][A-Z0-9_-]*", field="document_id")
    return cleaned


def _validate_query(query: str) -> str:
    """Validate a retrieval query (bounded, string)."""
    if not isinstance(query, str):
        raise ValidationError("query must be a string", field="query")
    cleaned = query.strip()
    if not cleaned:
        raise ValidationError("query must not be empty", field="query")
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise ValidationError(f"query exceeds {MAX_QUERY_LENGTH} characters", field="query")
    return cleaned


def _validate_top_k(top_k: int | None) -> int:
    """Bound and default the requested number of chunks."""
    if top_k is None:
        return DEFAULT_TOP_K
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise ValidationError("top_k must be an integer", field="top_k")
    if top_k < 1 or top_k > MAX_TOP_K:
        raise ValidationError(f"top_k must be between 1 and {MAX_TOP_K}", field="top_k")
    return top_k


class KnowledgeService:
    """Controlled, deterministic access to the stored knowledge corpus."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #
    async def ingest_corpus(self) -> KnowledgeIngestOut:
        """Ingest the curated corpus deterministically (idempotent upsert).

        Chunks are one-per-section (stable chunking). Every chunk stores its
        sparse TF vector (embedding under the corpus-wide IDF) and content
        hash, so retrieval is a pure read + score and corpus changes are
        detectable. Chunks absent from the current corpus are removed, keeping
        the index exactly in sync with the declared corpus version.
        """
        if not KNOWLEDGE_CORPUS:
            raise ValidationError("knowledge corpus is empty", field="corpus")

        all_contents = [
            str(section["content"])
            for document in KNOWLEDGE_CORPUS
            for section in document["sections"]
        ]
        idf = embeddings.build_idf(all_contents)

        documents_seen = len(KNOWLEDGE_CORPUS)
        documents_inserted = 0
        documents_updated = 0
        chunks_inserted = 0
        chunks_updated = 0

        seen_document_ids: set[str] = set()
        for document in KNOWLEDGE_CORPUS:
            document_id = _validate_document_id(str(document["document_id"]))
            seen_document_ids.add(document_id)
            values = {
                "document_type": str(document["document_type"]),
                "title": str(document["title"]),
                "jurisdiction": str(document["jurisdiction"]),
                "effective_date": str(document["effective_date"]),
                "version": int(document["version"]),
                "source": str(document["source"]),
                "sections": [
                    {"section": str(s["section"]), "content": str(s["content"])}
                    for s in document["sections"]
                ],
            }
            existing = await self.session.scalar(
                select(KnowledgeDocument).where(KnowledgeDocument.document_id == document_id)
            )
            if existing is None:
                self.session.add(KnowledgeDocument(document_id=document_id, **values))
                documents_inserted += 1
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
                documents_updated += 1

            for index, section in enumerate(values["sections"]):
                chunk_id = f"{document_id}::{_slugify(section['section'])}"
                content = section["content"]
                vector = embeddings.embed(content, idf)
                chunk_values = {
                    "section": section["section"],
                    "content": content,
                    "term_freq": dict(vector),
                    "content_hash": _chunk_hash(document_id, section["section"], content),
                    "chunk_index": index,
                }
                existing_chunk = await self.session.scalar(
                    select(KnowledgeChunk).where(KnowledgeChunk.chunk_id == chunk_id)
                )
                if existing_chunk is None:
                    self.session.add(
                        KnowledgeChunk(document_id=document_id, chunk_id=chunk_id, **chunk_values)
                    )
                    chunks_inserted += 1
                elif existing_chunk.content_hash != chunk_values["content_hash"]:
                    for key, value in chunk_values.items():
                        setattr(existing_chunk, key, value)
                    chunks_updated += 1

        # Remove chunks of documents/sections no longer in the corpus.
        stale = (
            (
                await self.session.execute(
                    select(KnowledgeChunk.chunk_id).where(
                        KnowledgeChunk.document_id.not_in(seen_document_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        if stale:
            await self.session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.chunk_id.in_(stale))
            )

        await self.session.flush()
        logger.info(
            "knowledge_corpus_ingested: docs=%s chunks_inserted=%s chunks_updated=%s terms=%s",
            documents_seen,
            chunks_inserted,
            chunks_updated,
            len(idf),
        )
        return KnowledgeIngestOut(
            documents_seen=documents_seen,
            documents_inserted=documents_inserted,
            documents_updated=documents_updated,
            chunks_inserted=chunks_inserted,
            chunks_updated=chunks_updated,
            index_terms=len(idf),
            corpus_version=CORPUS_VERSION,
        )

    # ------------------------------------------------------------------ #
    # Internal loaders
    # ------------------------------------------------------------------ #
    async def _load_chunks(self) -> list[dict[str, Any]]:
        """All chunk rows + document metadata (small corpus: full scan is fine
        and keeps ranking deterministic without server-side text search)."""
        rows = (
            await self.session.execute(
                select(KnowledgeChunk, KnowledgeDocument)
                .join(
                    KnowledgeDocument,
                    KnowledgeChunk.document_id == KnowledgeDocument.document_id,
                )
                .order_by(KnowledgeChunk.chunk_id)
            )
        ).all()
        return [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "section": chunk.section,
                "content": chunk.content,
                "term_freq": dict(chunk.term_freq or {}),
                "document_title": document.title,
                "document_type": document.document_type,
                "jurisdiction": document.jurisdiction,
                "effective_date": document.effective_date,
                "version": document.version,
            }
            for chunk, document in rows
        ]

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    async def search(self, query: str, top_k: int | None = None) -> KnowledgeSearchOut:
        """Rank chunks against the query (TF-IDF cosine, deterministic).

        Ties break by chunk_id; an empty result is a valid, explicit outcome.
        """
        cleaned_query = _validate_query(query)
        limit = _validate_top_k(top_k)

        chunks = await self._load_chunks()
        idf = embeddings.build_idf([chunk["content"] for chunk in chunks])
        query_vector = embeddings.embed(cleaned_query, idf)

        scored = [
            (
                embeddings.cosine_similarity(query_vector, chunk["term_freq"]),
                chunk,
            )
            for chunk in chunks
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))

        results = [
            KnowledgeChunkOut(
                chunk_id=chunk["chunk_id"],
                document_id=chunk["document_id"],
                document_title=chunk["document_title"],
                document_type=chunk["document_type"],
                section=chunk["section"],
                jurisdiction=chunk["jurisdiction"],
                effective_date=chunk["effective_date"],
                version=chunk["version"],
                content=chunk["content"],
                score=round(score, 6),
            )
            for score, chunk in scored[:limit]
            if score > MIN_SCORE
        ]
        return KnowledgeSearchOut(query=cleaned_query, results=results, count=len(results))

    async def get_document(self, document_id: str) -> KnowledgeDocumentOut:
        """Full stored document by id (NotFoundError when absent)."""
        cleaned = _validate_document_id(document_id)
        document = await self.session.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.document_id == cleaned)
        )
        if document is None:
            raise NotFoundError("knowledge_document", cleaned)
        return KnowledgeDocumentOut(
            document_id=document.document_id,
            document_type=document.document_type,
            title=document.title,
            jurisdiction=document.jurisdiction,
            effective_date=document.effective_date,
            version=document.version,
            source=document.source,
            sections=list(document.sections or []),
        )

    async def get_document_section(self, document_id: str, section: str) -> KnowledgeSectionOut:
        """One section of a stored document (exact, then case-insensitive)."""
        cleaned_document = _validate_document_id(document_id)
        cleaned_section = (section or "").strip()
        if not cleaned_section:
            raise ValidationError("section must not be empty", field="section")

        document = await self.session.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.document_id == cleaned_document)
        )
        if document is None:
            raise NotFoundError("knowledge_document", cleaned_document)

        sections = list(document.sections or [])
        matches = [s for s in sections if s.get("section") == cleaned_section]
        if not matches:
            lowered = cleaned_section.lower()
            case_matches = [s for s in sections if str(s.get("section", "")).lower() == lowered]
            if len(case_matches) == 1:
                matches = case_matches
            elif len(case_matches) > 1:
                raise ValidationError(
                    "section name is ambiguous (multiple case variants)",
                    field="section",
                )
        if not matches:
            raise NotFoundError("knowledge_section", f"{cleaned_document}#{cleaned_section}")

        section_data = matches[0]
        return KnowledgeSectionOut(
            document_id=document.document_id,
            document_title=document.title,
            document_type=document.document_type,
            section=str(section_data["section"]),
            content=str(section_data["content"]),
            jurisdiction=document.jurisdiction,
            effective_date=document.effective_date,
            version=document.version,
        )

    # ------------------------------------------------------------------ #
    # Corpus stats (operational, non-sensitive)
    # ------------------------------------------------------------------ #
    async def corpus_stats(self) -> dict[str, Any]:
        """Small summary of the stored knowledge index."""
        document_count = len(
            (await self.session.execute(select(KnowledgeDocument.document_id))).scalars().all()
        )
        chunk_rows = (
            (
                await self.session.execute(
                    select(KnowledgeChunk.content).order_by(KnowledgeChunk.chunk_id)
                )
            )
            .scalars()
            .all()
        )
        idf = embeddings.build_idf(list(chunk_rows))
        return {
            "documents": document_count,
            "chunks": len(chunk_rows),
            "index_terms": len(idf),
            "index_version": KNOWLEDGE_INDEX_VERSION,
            "corpus_version": CORPUS_VERSION,
        }
