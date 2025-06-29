class ConflictError(Exception):
    """Raised when there is a conflict, such as trying to add a duplicate object."""


class NotFoundError(Exception):
    """Raised when an object is not found in the store."""


class LockError(Exception):
    """Raised when there is an issue with acquiring a lock"""
