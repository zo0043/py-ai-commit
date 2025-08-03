"""
AI Commit exceptions module.

This module defines custom exceptions for the ai-commit tool.
"""


class AICommitError(Exception):
    """Base exception for all ai-commit related errors."""
    pass


class ConfigurationError(AICommitError):
    """Raised when there are configuration-related issues."""
    pass


class GitOperationError(AICommitError):
    """Raised when git operations fail."""
    pass


class APIError(AICommitError):
    """Raised when AI API calls fail."""
    pass


class SecurityError(AICommitError):
    """Raised when security-related operations fail."""
    pass


class ValidationError(AICommitError):
    """Raised when input validation fails."""
    pass


class FileOperationError(AICommitError):
    """Raised when file operations fail."""
    pass


class PluginError(AICommitError):
    """Raised when plugin operations fail."""
    pass


class PluginLoadError(PluginError):
    """Raised when plugin loading fails."""
    pass


class PluginConfigError(PluginError):
    """Raised when plugin configuration is invalid."""
    pass
