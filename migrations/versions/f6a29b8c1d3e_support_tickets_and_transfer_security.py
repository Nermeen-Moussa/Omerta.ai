"""Support tickets, identity verification, and transfer security schema.

Revision ID: f6a29b8c1d3e
Revises: e5a19f3b8c2d
Create Date: 2026-10-05 11:00:00.000000

Adds:
- Transfer security columns to customers (hashed_transfer_password, transfer_status, transfer_failed_attempts, transfer_blocked_at, transfer_unblocked_at, require_transfer_password_change, national_id_number, identity_status)
- support_tickets table
- support_messages table
- identity_verifications table
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6a29b8c1d3e"
down_revision: str | None = "e5a19f3b8c2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add transfer security & identity verification columns to customers
    op.add_column("customers", sa.Column("hashed_transfer_password", sa.String(length=255), nullable=True))
    op.add_column("customers", sa.Column("transfer_status", sa.String(length=32), nullable=False, server_default="ACTIVE"))
    op.add_column("customers", sa.Column("transfer_failed_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("customers", sa.Column("transfer_blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customers", sa.Column("transfer_unblocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customers", sa.Column("require_transfer_password_change", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("customers", sa.Column("national_id_number", sa.String(length=64), nullable=True))
    op.add_column("customers", sa.Column("identity_status", sa.String(length=32), nullable=False, server_default="NOT_VERIFIED"))

    op.create_index("ix_customers_transfer_status", "customers", ["transfer_status"])
    op.create_index("ix_customers_identity_status", "customers", ["identity_status"])
    op.create_index("ix_customers_national_id_number", "customers", ["national_id_number"])

    # 2. support_tickets table
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False, server_default="TRANSFER_BLOCKED"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="HIGH"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_support_tickets_external_id", "support_tickets", ["external_id"], unique=True)
    op.create_index("ix_support_tickets_customer_id", "support_tickets", ["customer_id"])
    op.create_index("ix_support_tickets_account_id", "support_tickets", ["account_id"])
    op.create_index("ix_support_tickets_issue_type", "support_tickets", ["issue_type"])
    op.create_index("ix_support_tickets_priority", "support_tickets", ["priority"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])
    op.create_index("ix_support_tickets_assigned_user_id", "support_tickets", ["assigned_user_id"])

    # 3. support_messages table
    op.create_table(
        "support_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_role", sa.String(length=32), nullable=False, server_default="CUSTOMER"),
        sa.Column("sender_name", sa.String(length=255), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("attachment_url", sa.String(length=512), nullable=True),
        sa.Column("attachment_name", sa.String(length=255), nullable=True),
        sa.Column("attachment_type", sa.String(length=32), nullable=False, server_default="NONE"),
        sa.Column("is_read_by_recipient", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_support_messages_external_id", "support_messages", ["external_id"], unique=True)
    op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])
    op.create_index("ix_support_messages_sender_role", "support_messages", ["sender_role"])

    # 4. identity_verifications table
    op.create_table(
        "identity_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("national_id_number", sa.String(length=64), nullable=True),
        sa.Column("document_type", sa.String(length=32), nullable=False, server_default="NATIONAL_ID"),
        sa.Column("document_front_url", sa.String(length=512), nullable=True),
        sa.Column("document_back_url", sa.String(length=512), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_identity_verifications_external_id", "identity_verifications", ["external_id"], unique=True)
    op.create_index("ix_identity_verifications_customer_id", "identity_verifications", ["customer_id"])
    op.create_index("ix_identity_verifications_ticket_id", "identity_verifications", ["ticket_id"])
    op.create_index("ix_identity_verifications_national_id", "identity_verifications", ["national_id_number"])
    op.create_index("ix_identity_verifications_status", "identity_verifications", ["verification_status"])


def downgrade() -> None:
    op.drop_table("identity_verifications")
    op.drop_table("support_messages")
    op.drop_table("support_tickets")
    op.drop_column("customers", "identity_status")
    op.drop_column("customers", "national_id_number")
    op.drop_column("customers", "require_transfer_password_change")
    op.drop_column("customers", "transfer_unblocked_at")
    op.drop_column("customers", "transfer_blocked_at")
    op.drop_column("customers", "transfer_failed_attempts")
    op.drop_column("customers", "transfer_status")
    op.drop_column("customers", "hashed_transfer_password")
