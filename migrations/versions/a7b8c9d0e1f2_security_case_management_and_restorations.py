"""Security case management, ticket policy extensions, and transfer restorations schema.

Revision ID: a7b8c9d0e1f2
Revises: f6a29b8c1d3e
Create Date: 2026-10-05 13:30:00.000000

Adds:
- transfer_restorations table for immutable history of transfer privilege restorations
- Extended fields on support_tickets table (ticket_type, category, title, customer_message, opened_by, assigned_analyst_id, closed_at, resolution_reason, admin_notes, requires_identity_verification, identity_verification_status, requires_compliance_review, escalated_to_compliance, related_transaction_id, related_account_id, related_risk_assessment_id, restoration_requested, restoration_approved, restoration_approved_by, restoration_approved_at, customer_restoration_count_at_creation)
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a29b8c1d3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add extended columns to support_tickets
    op.add_column("support_tickets", sa.Column("ticket_type", sa.String(length=64), nullable=False, server_default="TRANSFER_PASSWORD_LOCK"))
    op.add_column("support_tickets", sa.Column("category", sa.String(length=64), nullable=True, server_default="SECURITY"))
    op.add_column("support_tickets", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("support_tickets", sa.Column("customer_message", sa.Text(), nullable=True))
    op.add_column("support_tickets", sa.Column("opened_by", sa.String(length=64), nullable=False, server_default="CUSTOMER"))
    op.add_column("support_tickets", sa.Column("assigned_analyst_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("support_tickets", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("support_tickets", sa.Column("resolution_reason", sa.Text(), nullable=True))
    op.add_column("support_tickets", sa.Column("admin_notes", sa.Text(), nullable=True))
    op.add_column("support_tickets", sa.Column("requires_identity_verification", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("support_tickets", sa.Column("identity_verification_status", sa.String(length=32), nullable=False, server_default="NOT_REQUIRED"))
    op.add_column("support_tickets", sa.Column("requires_compliance_review", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("support_tickets", sa.Column("escalated_to_compliance", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("support_tickets", sa.Column("related_transaction_id", sa.Integer(), sa.ForeignKey("transfers.id", ondelete="SET NULL"), nullable=True))
    op.add_column("support_tickets", sa.Column("related_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.add_column("support_tickets", sa.Column("related_risk_assessment_id", sa.String(length=64), nullable=True))
    op.add_column("support_tickets", sa.Column("restoration_requested", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("support_tickets", sa.Column("restoration_approved", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("support_tickets", sa.Column("restoration_approved_by", sa.String(length=255), nullable=True))
    op.add_column("support_tickets", sa.Column("restoration_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("support_tickets", sa.Column("customer_restoration_count_at_creation", sa.Integer(), nullable=False, server_default="0"))

    op.create_index("ix_support_tickets_ticket_type", "support_tickets", ["ticket_type"])
    op.create_index("ix_support_tickets_idv_status", "support_tickets", ["identity_verification_status"])
    op.create_index("ix_support_tickets_risk_assessment", "support_tickets", ["related_risk_assessment_id"])

    # 2. Create transfer_restorations table
    op.create_table(
        "transfer_restorations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("actor_name", sa.String(length=255), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("restoration_number", sa.Integer(), nullable=False),
        sa.Column("previous_state", sa.String(length=32), nullable=False, server_default="BLOCKED"),
        sa.Column("new_state", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("verification_reference", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_transfer_restorations_external_id", "transfer_restorations", ["external_id"], unique=True)
    op.create_index("ix_transfer_restorations_customer_id", "transfer_restorations", ["customer_id"])
    op.create_index("ix_transfer_restorations_ticket_id", "transfer_restorations", ["ticket_id"])
    op.create_index("ix_transfer_restorations_actor_role", "transfer_restorations", ["actor_role"])


def downgrade() -> None:
    op.drop_table("transfer_restorations")
    op.drop_index("ix_support_tickets_risk_assessment", "support_tickets")
    op.drop_index("ix_support_tickets_idv_status", "support_tickets")
    op.drop_index("ix_support_tickets_ticket_type", "support_tickets")
    op.drop_column("support_tickets", "customer_restoration_count_at_creation")
    op.drop_column("support_tickets", "restoration_approved_at")
    op.drop_column("support_tickets", "restoration_approved_by")
    op.drop_column("support_tickets", "restoration_approved")
    op.drop_column("support_tickets", "restoration_requested")
    op.drop_column("support_tickets", "related_risk_assessment_id")
    op.drop_column("support_tickets", "related_account_id")
    op.drop_column("support_tickets", "related_transaction_id")
    op.drop_column("support_tickets", "escalated_to_compliance")
    op.drop_column("support_tickets", "requires_compliance_review")
    op.drop_column("support_tickets", "identity_verification_status")
    op.drop_column("support_tickets", "requires_identity_verification")
    op.drop_column("support_tickets", "admin_notes")
    op.drop_column("support_tickets", "resolution_reason")
    op.drop_column("support_tickets", "closed_at")
    op.drop_column("support_tickets", "assigned_analyst_id")
    op.drop_column("support_tickets", "opened_by")
    op.drop_column("support_tickets", "customer_message")
    op.drop_column("support_tickets", "title")
    op.drop_column("support_tickets", "category")
    op.drop_column("support_tickets", "ticket_type")
