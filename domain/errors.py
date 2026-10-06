"""Domain errors raised by application services.

Services raise these instead of leaking SQLAlchemy exceptions or HTTP concepts.
The MCP transport layer maps them to structured, predictable tool errors.
"""

from typing import Any


class DomainError(Exception):
    """Base class for domain errors with a machine-readable code and payload."""

    code = "DOMAIN_ERROR"

    def __init__(self, message: str, **payload: Any) -> None:
        super().__init__(message)
        self.message = message
        self.payload: dict[str, Any] = {"error": self.code, **payload}

    def __str__(self) -> str:
        return f"{self.message} | {self.payload}"


class ValidationError(DomainError):
    """Input failed validation (empty/oversized ids, out-of-range limits)."""

    code = "VALIDATION_ERROR"


class NotFoundError(DomainError):
    """A requested resource does not exist."""

    code = "NOT_FOUND"

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            f"{resource} '{resource_id}' not found",
            resource=resource,
            id=resource_id,
        )


class ConflictError(DomainError):
    """The request conflicts with persisted state (fail-closed integrity)."""

    code = "CONFLICT"
