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
    
    def __init__(self, message: str, sensitive_details: list = None):
        """
        Initialize ValidationError with optional sensitive content details.
        
        Args:
            message: Error message
            sensitive_details: List of sensitive content details (optional)
                           Each detail is a dict with 'type', 'content', 'line_number' keys
        """
        super().__init__(message)
        self.sensitive_details = sensitive_details or []
        
    def has_sensitive_content(self) -> bool:
        """Check if this error contains sensitive content details."""
        return len(self.sensitive_details) > 0


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
