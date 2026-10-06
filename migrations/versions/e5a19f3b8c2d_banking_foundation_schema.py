"""banking foundation schema: users, customers, sessions, risk assessments, signals, case notes and dispositions

Revision ID: e5a19f3b8c2d
Revises: c8d3e6a71b45
Create Date: 2026-10-04 10:00:00.000000

Adds the banking intelligence schema foundation:
- users table for RBAC authentication
- customers table for profile management
- sessions table for login & session tracking
- risk_assessments & risk_signals tables for multi-signal risk evaluations
- case_notes & case_dispositions for analyst workflows
- columns on accounts, devices, ip_addresses, and transactions
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5a19f3b8c2d"
down_revision: str | None = "c8d3e6a71b45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="FRAUD_ANALYST"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
    op.create_index("ix_users_external_id", "users", ["external_id"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # 2. Customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("customer_type", sa.String(length=32), nullable=False, server_default="INDIVIDUAL"),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="EG"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="LOW"),
        sa.Column("registration_date", sa.DateTime(timezone=True), nullable=False),
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
    op.create_index("ix_customers_external_id", "customers", ["external_id"], unique=True)
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_index("ix_customers_type", "customers", ["customer_type"])
    op.create_index("ix_customers_country", "customers", ["country"])
    op.create_index("ix_customers_risk", "customers", ["risk_level"])

    # 3. Enhance Accounts table
    op.add_column("accounts", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("currency", sa.String(length=3), nullable=False, server_default="EGP"))
    op.add_column("accounts", sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0.00"))
    op.create_foreign_key(
        "fk_accounts_customer_id",
        "accounts",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_accounts_customer_id", "accounts", ["customer_id"])
    op.create_index("ix_accounts_currency", "accounts", ["currency"])

    # 4. Enhance Devices table
    op.add_column("devices", sa.Column("platform", sa.String(length=32), nullable=False, server_default="Android"))
    op.add_column("devices", sa.Column("user_agent", sa.String(length=255), nullable=True))
    op.add_column("devices", sa.Column("is_emulator", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("devices", sa.Column("is_rooted", sa.Boolean(), nullable=False, server_default="false"))

    # 5. Enhance IP Addresses table
    op.add_column("ip_addresses", sa.Column("is_vpn", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("ip_addresses", sa.Column("is_proxy", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("ip_addresses", sa.Column("is_datacenter", sa.Boolean(), nullable=False, server_default="false"))

    # 6. Sessions table
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("ip_address_id", sa.Integer(), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("is_vpn", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_emulator", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ip_address_id"], ["ip_addresses.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_sessions_external_id", "sessions", ["external_id"], unique=True)
    op.create_index("ix_sessions_customer_id", "sessions", ["customer_id"])
    op.create_index("ix_sessions_account_id", "sessions", ["account_id"])
    op.create_index("ix_sessions_device_id", "sessions", ["device_id"])
    op.create_index("ix_sessions_ip_address_id", "sessions", ["ip_address_id"])

    # 7. Enhance Transactions table
    op.add_column("transactions", sa.Column("risk_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("transactions", sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="LOW"))
    op.add_column("transactions", sa.Column("review_status", sa.String(length=32), nullable=False, server_default="NOT_REQUIRED"))
    op.create_index("ix_transactions_risk_score", "transactions", ["risk_score"])
    op.create_index("ix_transactions_review_status", "transactions", ["review_status"])
    op.create_index("ix_transactions_currency", "transactions", ["currency"])

    # 7b. Alter Alerts risk_score type to accommodate 0-100 score scale
    op.alter_column("alerts", "risk_score", type_=sa.Numeric(6, 2))

    # 8. Risk Assessments table
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("risk_level", sa.String(length=24), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="COMPLETED"),
        sa.Column("version", sa.String(length=16), nullable=False, server_default="v1.0"),
        sa.Column("correlation_id", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_risk_assessments_external_id", "risk_assessments", ["external_id"], unique=True)
    op.create_index("ix_risk_assessments_transaction_id", "risk_assessments", ["transaction_id"])
    op.create_index("ix_risk_assessments_requires_review", "risk_assessments", ["requires_human_review"])
    op.create_index("ix_risk_assessments_correlation_id", "risk_assessments", ["correlation_id"])

    # 9. Risk Signals table
    op.create_table(
        "risk_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("signal_name", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default="1.000"),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["risk_assessments.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_risk_signals_assessment_id", "risk_signals", ["assessment_id"])
    op.create_index("ix_risk_signals_signal_name", "risk_signals", ["signal_name"])
    op.create_index("ix_risk_signals_severity", "risk_signals", ["severity"])
    op.create_index("ix_risk_signals_source", "risk_signals", ["source"])

    # 10. Enhance Investigation Cases
    op.add_column("investigation_cases", sa.Column("transaction_id", sa.Integer(), nullable=True))
    op.add_column("investigation_cases", sa.Column("title", sa.String(length=255), nullable=False, server_default="Financial Crime Investigation"))
    op.alter_column("investigation_cases", "alert_id", nullable=True)
    op.create_foreign_key(
        "fk_cases_transaction_id",
        "investigation_cases",
        "transactions",
        ["transaction_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_investigation_cases_transaction_id", "investigation_cases", ["transaction_id"])

    # 11. Case Notes table
    op.create_table(
        "case_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["case_id"], ["investigation_cases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_case_notes_case_id", "case_notes", ["case_id"])

    # 12. Case Dispositions table
    op.create_table(
        "case_dispositions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("analyst_id", sa.String(length=255), nullable=False),
        sa.Column("disposition", sa.String(length=64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["case_id"], ["investigation_cases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_case_dispositions_case_id", "case_dispositions", ["case_id"])
    op.create_index("ix_case_dispositions_analyst_id", "case_dispositions", ["analyst_id"])
    op.create_index("ix_case_dispositions_disposition", "case_dispositions", ["disposition"])

    # 13. Enhance Audit Events
    op.alter_column("audit_events", "case_id", nullable=True)
    op.add_column("audit_events", sa.Column("actor_id", sa.String(length=255), nullable=True))
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])


def downgrade() -> None:
    # 13. Revert Audit Events
    op.drop_index("ix_audit_events_actor_id", "audit_events")
    op.drop_column("audit_events", "actor_id")
    op.alter_column("audit_events", "case_id", nullable=False)

    # 12. Drop Case Dispositions
    op.drop_table("case_dispositions")

    # 11. Drop Case Notes
    op.drop_table("case_notes")

    # 10. Revert Investigation Cases
    op.drop_index("ix_investigation_cases_transaction_id", "investigation_cases")
    op.drop_constraint("fk_cases_transaction_id", "investigation_cases", type_="foreignkey")
    op.drop_column("investigation_cases", "title")
    op.drop_column("investigation_cases", "transaction_id")
    op.alter_column("investigation_cases", "alert_id", nullable=False)

    # 9. Drop Risk Signals
    op.drop_table("risk_signals")

    # 8. Drop Risk Assessments
    op.drop_table("risk_assessments")

    # 7b. Revert Alerts risk_score
    op.alter_column("alerts", "risk_score", type_=sa.Numeric(3, 2))

    # 7. Revert Transactions
    op.drop_index("ix_transactions_currency", "transactions")
    op.drop_index("ix_transactions_review_status", "transactions")
    op.drop_index("ix_transactions_risk_score", "transactions")
    op.drop_column("transactions", "review_status")
    op.drop_column("transactions", "risk_level")
    op.drop_column("transactions", "risk_score")

    # 6. Drop Sessions
    op.drop_table("sessions")

    # 5. Revert IP Addresses
    op.drop_column("ip_addresses", "is_datacenter")
    op.drop_column("ip_addresses", "is_proxy")
    op.drop_column("ip_addresses", "is_vpn")

    # 4. Revert Devices
    op.drop_column("devices", "is_rooted")
    op.drop_column("devices", "is_emulator")
    op.drop_column("devices", "user_agent")
    op.drop_column("devices", "platform")

    # 3. Revert Accounts
    op.drop_index("ix_accounts_currency", "accounts")
    op.drop_index("ix_accounts_customer_id", "accounts")
    op.drop_constraint("fk_accounts_customer_id", "accounts", type_="foreignkey")
    op.drop_column("accounts", "balance")
    op.drop_column("accounts", "currency")
    op.drop_column("accounts", "customer_id")

    # 2. Drop Customers
    op.drop_table("customers")

    # 1. Drop Users
    op.drop_table("users")
