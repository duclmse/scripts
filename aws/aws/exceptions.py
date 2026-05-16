"""Custom exception hierarchy for the AWS CLI utility."""
from __future__ import annotations


class AWSCLIError(Exception):
    """Base class for all AWS CLI errors."""

    exit_code: int = 1

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.details = details


class AuthError(AWSCLIError):
    """Authentication or authorisation failure."""

    exit_code = 2


class ConfigError(AWSCLIError):
    """Configuration file is missing or invalid."""

    exit_code = 3


class CacheError(AWSCLIError):
    """Cache read/write operation failed."""

    exit_code = 4


class DryRunAbort(AWSCLIError):
    """Mutating operation blocked because dry-run mode is active."""

    exit_code = 0


class PluginError(AWSCLIError):
    """Plugin failed to load or its command raised an error."""

    exit_code = 5


class ResourceNotFoundError(AWSCLIError):
    """Referenced AWS resource does not exist."""

    exit_code = 6


class ValidationError(AWSCLIError):
    """CLI input failed validation."""

    exit_code = 8
