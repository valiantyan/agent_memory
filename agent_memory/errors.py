"""CLI exit codes (DESIGN §6)."""

from __future__ import annotations


class MemoryError(Exception):
    """Base error with exit code."""

    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UsageError(MemoryError):
    exit_code = 2


class SchemaError(MemoryError):
    exit_code = 3


class SecurityError(MemoryError):
    exit_code = 4


class ConflictError(MemoryError):
    """Quota / id conflict / project gate."""

    exit_code = 5


class NotFoundError(MemoryError):
    exit_code = 6
