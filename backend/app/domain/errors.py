class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status = 400


class NotFound(DomainError):
    code = "NOT_FOUND"
    status = 404


class StaleSnapshotError(DomainError):
    code = "STALE_RESULT"
    status = 409


class PermissionDenied(DomainError):
    code = "PERMISSION_DENIED"
    status = 403


class ApprovalRequired(DomainError):
    code = "APPROVAL_REQUIRED"
    status = 403


class Conflict(DomainError):
    code = "CONFLICT"
    status = 409


class CapabilityUnavailable(DomainError):
    code = "CAPABILITY_UNAVAILABLE"
    status = 503


class ProviderError(DomainError):
    code = "PROVIDER_ERROR"
    status = 502


class TransientProviderError(ProviderError):
    code = "TRANSIENT_PROVIDER_ERROR"


class ExternalSystemUnavailable(ProviderError):
    code = "EXTERNAL_SYSTEM_UNAVAILABLE"


class WorkflowError(DomainError):
    code = "WORKFLOW_ERROR"
    status = 503
