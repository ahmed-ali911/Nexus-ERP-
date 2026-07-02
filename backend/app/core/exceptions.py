class NotFoundError(Exception):
    """Raised by a service layer when a requested entity does not exist."""


class AuthenticationError(Exception):
    """Raised when login/token credentials are invalid, expired, or locked out."""


class BusinessRuleViolation(Exception):
    """Raised when an action is well-formed but violates a domain rule
    (e.g. assigning a role from another company, deleting your own account).
    """
