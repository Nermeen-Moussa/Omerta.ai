"""phase 12 knowledge documents and chunks

Revision ID: c8d3e6a71b45
Revises: b41c7e5d9f02
Create Date: 2026-09-28 12:00:00.000000

Adds the Knowledge MCP storage layer: curated knowledge_documents (policy /
regulation / typology / procedure reference data) and their indexed
knowledge_chunks (one per section, with a stored sparse TF vector and content
hash so retrieval is deterministic and corpus changes are detectable).
Non-destructive: existing tables are untouched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8d3e6a71b45"
down_revision: str | None = "b41c7e5d9f02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("jurisdiction", sa.String(length=16), nullable=False, server_default="GLOBAL"),
        sa.Column("effective_date", sa.String(length=10), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_knowledge_documents_document_id", "knowledge_documents", ["document_id"], unique=True
    )
    op.create_index("ix_knowledge_documents_type", "knowledge_documents", ["document_type"])
    op.create_index("ix_knowledge_documents_jurisdiction", "knowledge_documents", ["jurisdiction"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chunk_id", sa.String(length=140), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("section", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("term_freq", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["knowledge_documents.document_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("document_id", "section", name="uq_knowledge_doc_section"),
    )
    op.create_index("ix_knowledge_chunks_chunk_id", "knowledge_chunks", ["chunk_id"], unique=True)
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_content_hash", "knowledge_chunks", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_content_hash", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_chunk_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_documents_jurisdiction", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_type", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_document_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
