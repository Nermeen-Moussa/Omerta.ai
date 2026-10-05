"""Master v1 API Router for Omerta.ai Banking Intelligence Platform."""

from fastapi import APIRouter

from apps.api.v1.accounts import router as accounts_router
from apps.api.v1.admin import router as admin_router
from apps.api.v1.audit import router as audit_router
from apps.api.v1.auth import router as auth_router
from apps.api.v1.cases import router as cases_router
from apps.api.v1.customer import router as customer_router
from apps.api.v1.customers import router as customers_router
from apps.api.v1.dashboard import router as dashboard_router
from apps.api.v1.devices import router as devices_router
from apps.api.v1.network import router as network_router
from apps.api.v1.reports import router as reports_router
from apps.api.v1.risk import router as risk_router
from apps.api.v1.settings import router as settings_router
from apps.api.v1.support import router as support_router
from apps.api.v1.tickets import (
    admin_tickets_router,
    customer_tickets_router,
)
from apps.api.v1.transactions import router as transactions_router

api_v1_router = APIRouter(prefix="/api/v1")

# Authentication & Registration
api_v1_router.include_router(auth_router)

# Customer Banking Platform (Dedicated Customer Endpoints)
api_v1_router.include_router(customer_router)
api_v1_router.include_router(customer_tickets_router)

# Admin Control Center (Dedicated Admin Endpoints)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(admin_tickets_router)

# Support & Security Cases (Customer & Admin Helpdesk / Chat / ID Verification)
api_v1_router.include_router(support_router)

# Financial Crime Intelligence & Platform Modules
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(transactions_router)
api_v1_router.include_router(customers_router)
api_v1_router.include_router(accounts_router)
api_v1_router.include_router(devices_router)
api_v1_router.include_router(network_router)
api_v1_router.include_router(risk_router)
api_v1_router.include_router(cases_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(settings_router)

