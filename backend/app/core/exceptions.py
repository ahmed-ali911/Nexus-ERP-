class NotFoundError(Exception):
    """Raised by a service layer when a requested entity does not exist."""


class AuthenticationError(Exception):
    """Raised when login/token credentials are invalid, expired, or locked out."""


class BusinessRuleViolation(Exception):
    """Raised when an action is well-formed but violates a domain rule
    (e.g. assigning a role from another company, deleting your own account).
    """


class ApprovalRequired(Exception):
    """Raised when an operation is blocked pending manager approval.

    The caller should create an ApprovalRequest row before raising this;
    approval_request_id identifies that row so the API can return it.
    """

    def __init__(self, approval_request_id: int, detail: str) -> None:
        super().__init__(detail)
        self.approval_request_id = approval_request_id
        self.detail = detail
