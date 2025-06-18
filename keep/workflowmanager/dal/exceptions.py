class ConflictError(Exception):
    """Raised when there is a conflict, such as trying to add a duplicate object."""


class LockError(Exception):
    """Raised when there is an issue with acquiring a lock"""
