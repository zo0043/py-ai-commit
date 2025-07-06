"""
Security utilities for AI Commit.

This module provides secure storage and management of sensitive data like API keys.
"""

import re
import logging
from typing import Optional, Dict, Any
import keyring
from ..exceptions import SecurityError, ValidationError

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Secure API key management using system keyring."""
    
    SERVICE_NAME = "ai-commit"
    
    def __init__(self):
        """Initialize the API key manager."""
        try:
            # Test keyring availability
            keyring.get_keyring()
        except Exception as e:
            logger.warning(f"Keyring not available: {e}")
    
    def store_api_key(self, provider: str, api_key: str) -> None:
        """
        Store API key securely in system keyring.
        
        Args:
            provider: The AI provider name (e.g., 'openai')
            api_key: The API key to store
            
        Raises:
            SecurityError: If keyring storage fails
        """
        try:
            keyring.set_password(self.SERVICE_NAME, provider, api_key)
            logger.info(f"API key for {provider} stored securely")
        except Exception as e:
            raise SecurityError(f"Failed to store API key for {provider}: {e}")
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Retrieve API key from secure storage.
        
        Args:
            provider: The AI provider name
            
        Returns:
            The API key if found, None otherwise
            
        Raises:
            SecurityError: If keyring access fails
        """
        try:
            api_key = keyring.get_password(self.SERVICE_NAME, provider)
            if api_key:
                logger.debug(f"Retrieved API key for {provider} from secure storage")
            return api_key
        except Exception as e:
            raise SecurityError(f"Failed to retrieve API key for {provider}: {e}")
    
    def delete_api_key(self, provider: str) -> None:
        """
        Delete API key from secure storage.
        
        Args:
            provider: The AI provider name
            
        Raises:
            SecurityError: If keyring deletion fails
        """
        try:
            keyring.delete_password(self.SERVICE_NAME, provider)
            logger.info(f"API key for {provider} deleted from secure storage")
        except Exception as e:
            raise SecurityError(f"Failed to delete API key for {provider}: {e}")


class InputValidator:
    """Input validation and sanitization utilities."""
    
    # Patterns for detecting sensitive information
    SENSITIVE_PATTERNS = [
        r'(?i)(api[_\s-]?key|secret|token|password)\s*[:=]\s*[\'"]*([a-zA-Z0-9\-_]+)',
        r'(?i)(bearer|authorization)\s*:\s*[\'"]*([a-zA-Z0-9\-_\.]+)',
        r'(?i)sk-[a-zA-Z0-9]{20,}',  # OpenAI API key pattern
        r'(?i)xoxb-[a-zA-Z0-9\-]+',  # Slack token pattern
        r'(?i)ghp_[a-zA-Z0-9]{36}',  # GitHub personal access token
    ]
    
    MAX_DIFF_SIZE = 1024 * 1024  # 1MB max diff size
    MAX_COMMIT_MESSAGE_LENGTH = 200
    
    @classmethod
    def validate_git_diff(cls, diff: str) -> str:
        """
        Validate and sanitize git diff content.
        
        Args:
            diff: The git diff content
            
        Returns:
            Sanitized diff content
            
        Raises:
            ValidationError: If diff contains issues
        """
        if not diff or not diff.strip():
            raise ValidationError("Empty git diff provided")
        
        if len(diff) > cls.MAX_DIFF_SIZE:
            raise ValidationError(f"Git diff too large: {len(diff)} bytes (max: {cls.MAX_DIFF_SIZE})")
        
        # Check for sensitive information
        cls._check_for_sensitive_data(diff, "git diff")
        
        return diff.strip()
    
    @classmethod
    def validate_commit_message(cls, message: str) -> str:
        """
        Validate generated commit message.
        
        Args:
            message: The commit message to validate
            
        Returns:
            Validated commit message
            
        Raises:
            ValidationError: If message is invalid
        """
        if not message or not message.strip():
            raise ValidationError("Empty commit message")
        
        message = message.strip()
        
        if len(message) > cls.MAX_COMMIT_MESSAGE_LENGTH:
            raise ValidationError(
                f"Commit message too long: {len(message)} chars (max: {cls.MAX_COMMIT_MESSAGE_LENGTH})"
            )
        
        # Check for sensitive information in commit message
        cls._check_for_sensitive_data(message, "commit message")
        
        return message
    
    @classmethod
    def validate_api_key(cls, api_key: str, provider: str = "openai") -> str:
        """
        Validate API key format.
        
        Args:
            api_key: The API key to validate
            provider: The provider name
            
        Returns:
            Validated API key
            
        Raises:
            ValidationError: If API key format is invalid
        """
        if not api_key or not api_key.strip():
            raise ValidationError("Empty API key")
        
        api_key = api_key.strip()
        
        if provider.lower() == "openai":
            if not api_key.startswith(('sk-', 'sk-proj-')):
                raise ValidationError("Invalid OpenAI API key format")
            
            if len(api_key) < 20:
                raise ValidationError("OpenAI API key too short")
        
        return api_key
    
    @classmethod
    def _check_for_sensitive_data(cls, content: str, content_type: str) -> None:
        """
        Check content for sensitive information patterns.
        
        Args:
            content: Content to check
            content_type: Type of content for error messages
            
        Raises:
            ValidationError: If sensitive data is detected
        """
        for pattern in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, content):
                logger.warning(f"Sensitive data pattern detected in {content_type}")
                raise ValidationError(
                    f"Potential sensitive information detected in {content_type}. "
                    "Please review and remove any API keys, tokens, or passwords."
                )


class SecureLogger:
    """Logger wrapper that filters sensitive information."""
    
    def __init__(self, logger: logging.Logger):
        """Initialize secure logger wrapper."""
        self.logger = logger
        self.validator = InputValidator()
    
    def log_safe(self, level: int, message: str, details: Optional[str] = None) -> None:
        """
        Log message after filtering sensitive information.
        
        Args:
            level: Log level
            message: Log message
            details: Additional details
        """
        # Filter sensitive information from message
        safe_message = self._filter_sensitive_info(message)
        safe_details = self._filter_sensitive_info(details) if details else None
        
        extra = {'details': safe_details if safe_details else 'No additional details'}
        self.logger.log(level, safe_message, extra=extra)
    
    def _filter_sensitive_info(self, text: str) -> str:
        """
        Filter sensitive information from text.
        
        Args:
            text: Text to filter
            
        Returns:
            Filtered text with sensitive info redacted
        """
        if not text:
            return text
        
        filtered = text
        for pattern in InputValidator.SENSITIVE_PATTERNS:
            filtered = re.sub(pattern, r'\1: [REDACTED]', filtered, flags=re.IGNORECASE)
        
        return filtered


def mask_api_key(api_key: str) -> str:
    """
    Mask API key for safe display.
    
    Args:
        api_key: The API key to mask
        
    Returns:
        Masked API key showing only first and last few characters
    """
    if not api_key or len(api_key) < 8:
        return "[REDACTED]"
    
    return f"{api_key[:4]}...{api_key[-4:]}"