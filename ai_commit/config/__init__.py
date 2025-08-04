"""
Configuration management for AI Commit.

This module handles loading, validation, and management of configuration settings.
"""

import os
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dotenv import load_dotenv

from ..exceptions import ConfigurationError
from ..security import APIKeyManager, InputValidator, mask_api_key

logger = logging.getLogger(__name__)


class ConfigurationCache:
    """Simple cache for configuration validation."""
    
    def __init__(self, ttl: float = 300.0):  # 5 minutes
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set cached value."""
        self._cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()


# Global configuration cache
_config_cache = ConfigurationCache()


@dataclass
class AICommitConfig:
    """Configuration data class for AI Commit."""

    # Required settings
    openai_api_key: str
    openai_base_url: str
    openai_model: str

    # Optional settings with defaults
    log_path: str = ".commitLogs"
    auto_commit: bool = False
    auto_push: bool = False
    max_retries: int = 3
    timeout: int = 30
    use_secure_storage: bool = True

    # Internal settings
    _api_key_manager: Optional[APIKeyManager] = field(default=None, init=False)

    def __post_init__(self):
        """Post-initialization validation and setup."""
        self._api_key_manager = APIKeyManager()
        self.validate()

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            # Validate required fields
            if not self.openai_api_key:
                raise ConfigurationError("OPENAI_API_KEY is required")

            if not self.openai_base_url:
                raise ConfigurationError("OPENAI_BASE_URL is required")

            if not self.openai_model:
                raise ConfigurationError("OPENAI_MODEL is required")

            # Validate API key format
            InputValidator.validate_api_key(self.openai_api_key, "openai")

            # Validate URL format
            if not self.openai_base_url.startswith(('http://', 'https://')):
                raise ConfigurationError("OPENAI_BASE_URL must be a valid URL")

            # Validate model name
            valid_models = [
                'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
                'gpt-3.5-turbo-16k', 'gpt-4-32k',
                'glm-4', 'glm-4-flash', 'glm-4-plus', 'glm-4v', 'glm-4v-plus'
            ]
            if self.openai_model not in valid_models:
                logger.warning(
                    f"Using potentially unsupported model '{self.openai_model}'. "
                    f"Supported models: {', '.join(valid_models)}"
                )

            # Validate numeric settings
            if self.max_retries < 1 or self.max_retries > 10:
                raise ConfigurationError("max_retries must be between 1 and 10")

            if self.timeout < 5 or self.timeout > 300:
                raise ConfigurationError("timeout must be between 5 and 300 seconds")

            logger.debug("Configuration validation passed")

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Configuration validation failed: {e}")

    def get_masked_config(self) -> Dict[str, Any]:
        """
        Get configuration with sensitive values masked.

        Returns:
            Dictionary with masked sensitive information
        """
        return {
            'openai_api_key': mask_api_key(self.openai_api_key),
            'openai_base_url': self.openai_base_url,
            'openai_model': self.openai_model,
            'log_path': self.log_path,
            'auto_commit': self.auto_commit,
            'auto_push': self.auto_push,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'use_secure_storage': self.use_secure_storage,
        }

    def store_api_key_securely(self) -> None:
        """Store API key in secure storage if enabled."""
        if self.use_secure_storage and self._api_key_manager:
            try:
                self._api_key_manager.store_api_key("openai", self.openai_api_key)
                logger.info("API key stored securely")
            except Exception as e:
                logger.warning(f"Failed to store API key securely: {e}")


class ConfigurationLoader:
    """Handles loading configuration from various sources."""

    ENV_VARS = [
        'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL',
        'LOG_PATH', 'AUTO_COMMIT', 'AUTO_PUSH', 'MAX_RETRIES', 'TIMEOUT'
    ]

    def __init__(self):
        """Initialize configuration loader."""
        self.api_key_manager = APIKeyManager()

    def load_config(self, config_path: Optional[str] = None) -> AICommitConfig:
        """
        Load configuration from all available sources.

        Configuration priority (highest to lowest):
        1. Command-line arguments (handled by caller)
        2. Configuration files (.aicommit, .env)
        3. Secure storage (keyring)
        4. Environment variables

        Args:
            config_path: Optional path to specific config file

        Returns:
            Loaded and validated configuration

        Raises:
            ConfigurationError: If configuration cannot be loaded or is invalid
        """
        config = {}
        config_sources = []

        # 1. Load from environment variables (lowest priority)
        env_config = self._load_from_environment()
        if env_config:
            config.update(env_config)
            config_sources.append("environment variables")
            logger.debug(f"Loaded configuration from environment: {', '.join(env_config.keys())}")

        # 2. Load from secure storage (medium priority)
        secure_config = self._load_from_secure_storage()
        if secure_config:
            config.update(secure_config)
            config_sources.append("secure storage")
            logger.debug("Loaded API key from secure storage")

        # 3. Load from configuration files (highest priority)
        config_type, config_file = self._find_config_files(config_path)
        if config_file:
            file_config = self._load_from_file(config_type, config_file)
            if file_config:
                config.update(file_config)
                config_sources.append(f"{config_type} file ({config_file})")
                logger.debug(f"Loaded configuration from {config_type} file: {config_file}")

        # 4. Validate we have required configuration
        if not config:
            self._show_configuration_help()
            raise ConfigurationError("No configuration found")

        # 5. Log configuration sources
        if config_sources:
            logger.info(f"Configuration loaded from: {' → '.join(config_sources)}")

        # 6. Check for potential configuration conflicts
        self._check_configuration_conflicts(config)

        # 7. Convert and validate configuration
        return self._create_config_object(config)

    def _load_from_environment(self) -> Dict[str, str]:
        """Load configuration from environment variables."""
        return self._get_environment_config()

    def _load_from_secure_storage(self) -> Dict[str, str]:
        """Load API key from secure storage."""
        try:
            api_key = self.api_key_manager.get_api_key("openai")
            if api_key:
                return {'OPENAI_API_KEY': api_key}
        except Exception as e:
            logger.debug(f"Could not load from secure storage: {e}")
        return {}

    def _check_environment_variables(self) -> bool:
        """
        Check if required environment variables are configured.
        
        Returns:
            True if environment variables are configured, False otherwise
        """
        # Check for ANTHROPIC_* variables (primary)
        anthropic_vars = [
            'ANTHROPIC_AUTH_TOKEN',
            'ANTHROPIC_BASE_URL',
            'ANTHROPIC_MODEL'
        ]
        
        # Check for OPENAI_* variables (fallback)
        openai_vars = [
            'OPENAI_API_KEY',
            'OPENAI_BASE_URL',
            'OPENAI_MODEL'
        ]
        
        # Check if either set is configured
        anthropic_configured = all(var in os.environ for var in anthropic_vars)
        openai_configured = all(var in os.environ for var in openai_vars)
        
        return anthropic_configured or openai_configured

    def _get_environment_config(self) -> Dict[str, str]:
        """
        Get configuration from environment variables with mapping.
        
        Returns:
            Configuration dictionary with mapped variable names
        """
        config = {}
        
        # Map ANTHROPIC_* variables to OPENAI_* variables
        if 'ANTHROPIC_AUTH_TOKEN' in os.environ:
            config['OPENAI_API_KEY'] = os.environ['ANTHROPIC_AUTH_TOKEN']
        elif 'OPENAI_API_KEY' in os.environ:
            config['OPENAI_API_KEY'] = os.environ['OPENAI_API_KEY']
            
        if 'ANTHROPIC_BASE_URL' in os.environ:
            config['OPENAI_BASE_URL'] = os.environ['ANTHROPIC_BASE_URL']
        elif 'OPENAI_BASE_URL' in os.environ:
            config['OPENAI_BASE_URL'] = os.environ['OPENAI_BASE_URL']
            
        if 'ANTHROPIC_MODEL' in os.environ:
            config['OPENAI_MODEL'] = os.environ['ANTHROPIC_MODEL']
        elif 'OPENAI_MODEL' in os.environ:
            config['OPENAI_MODEL'] = os.environ['OPENAI_MODEL']
        
        # Add optional variables
        for env_var, config_key in [
            ('LOG_PATH', 'LOG_PATH'),
            ('AUTO_COMMIT', 'AUTO_COMMIT'),
            ('AUTO_PUSH', 'AUTO_PUSH')
        ]:
            if env_var in os.environ:
                config[config_key] = os.environ[env_var]
        
        return config

    def _find_config_files(
            self, config_path: Optional[str] = None) -> Tuple[Optional[str], Optional[Path]]:
        """
        Find configuration files.

        Args:
            config_path: Optional specific config file path

        Returns:
            Tuple of (config_type, config_file_path)
        """
        if config_path:
            config_file = Path(config_path)
            if config_file.exists():
                return ('custom', config_file)
            else:
                raise ConfigurationError(f"Config file not found: {config_path}")

        current = Path.cwd()
        while current != current.parent:
            aicommit_file = current / '.aicommit'
            env_file = current / '.env'
            template_file = current / '.aicommit_template'

            if aicommit_file.exists():
                return ('aicommit', aicommit_file)
            elif env_file.exists():
                return ('env', env_file)
            elif template_file.exists():
                # Check if environment variables are available as fallback
                if not self._check_environment_variables():
                    raise ConfigurationError(
                        "Found .aicommit_template file. Please configure it and rename to .aicommit"
                    )

            current = current.parent

        # Only check environment variables if no config files found
        if self._check_environment_variables():
            return ('environment', None)

        return (None, None)

    def _load_from_file(self, config_type: str, config_file: Path) -> Dict[str, str]:
        """
        Load configuration from file.

        Args:
            config_type: Type of config file
            config_file: Path to config file

        Returns:
            Configuration dictionary
        """
        config = {}
        try:
            if config_type == 'environment':
                config = self._get_environment_config()
            elif config_type in ('aicommit', 'custom'):
                config = self._load_aicommit_config(config_file)
            else:  # env file
                load_dotenv(config_file)
                # Re-read environment variables after loading .env file
                for key in self.ENV_VARS:
                    value = os.getenv(key)
                    if value:
                        config[key] = value

            return config
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration from {config_file}: {e}")

    def _load_aicommit_config(self, config_file: Path) -> Dict[str, str]:
        """Load configuration from .aicommit file."""
        config = {}
        with open(config_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' not in line:
                    logger.warning(f"Invalid config line {line_num} in {config_file}: {line}")
                    continue

                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()

        return config

    def _create_config_object(self, config: Dict[str, str]) -> AICommitConfig:
        """
        Create AICommitConfig object from configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            AICommitConfig object
        """
        # Convert string values to appropriate types
        processed_config = {}

        # Required string fields
        for key in ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL']:
            if key in config:
                processed_config[key.lower()] = config[key]

        # Optional string fields
        if 'LOG_PATH' in config:
            processed_config['log_path'] = config['LOG_PATH']

        # Boolean fields
        for key in ['AUTO_COMMIT', 'AUTO_PUSH']:
            if key in config:
                processed_config[key.lower()] = config[key].lower() in ('true', '1', 'yes', 'on')

        # Integer fields
        for key in ['MAX_RETRIES', 'TIMEOUT']:
            if key in config:
                try:
                    processed_config[key.lower()] = int(config[key])
                except ValueError:
                    logger.warning(f"Invalid integer value for {key}: {config[key]}")

        try:
            return AICommitConfig(**processed_config)
        except TypeError as e:
            required_fields = ['openai_api_key', 'openai_base_url', 'openai_model']
            missing_fields = [field for field in required_fields if field not in processed_config]
            if missing_fields:
                raise ConfigurationError(
                    f"Missing required configuration: {', '.join(missing_fields)}")
            raise ConfigurationError(f"Invalid configuration: {e}")

    def _show_configuration_help(self) -> None:
        """Display helpful configuration instructions."""
        print("\n" + "=" * 60)
        print("❌ Configuration Required")
        print("=" * 60)
        print("No configuration found. You can configure ai-commit in multiple ways:")
        print("\n1. Environment Variables:")
        print("   export OPENAI_API_KEY='your-api-key'")
        print("   export OPENAI_BASE_URL='https://api.openai.com/v1'")
        print("   export OPENAI_MODEL='gpt-3.5-turbo'")
        print("\n2. Configuration File (.aicommit or .env):")
        print("   Create a file with your settings in the current directory")
        print("\n3. Secure Storage:")
        print("   Use 'ai-commit config set-key' to store API key securely")
        print("=" * 60)

    def _check_configuration_conflicts(self, config: Dict[str, Any]) -> None:
        """
        Check for potential configuration conflicts and log warnings.

        Args:
            config: Configuration dictionary
        """
        # Check for model compatibility
        model = config.get('openai_model', '')
        base_url = config.get('openai_base_url', '')

        # Warn if using OpenAI model with non-OpenAI base URL
        if 'gpt-' in model.lower() and 'openai.com' not in base_url.lower():
            logger.warning(
                f"Using OpenAI model '{model}' with non-OpenAI base URL '{base_url}'. "
                "This may not work as expected."
            )

        # Check for reasonable timeout values
        timeout = config.get('timeout', 30)
        if timeout < 10:
            logger.warning(f"Very short timeout ({timeout}s) may cause API calls to fail")
        elif timeout > 120:
            logger.warning(f"Very long timeout ({timeout}s) may cause poor user experience")

        # Check for reasonable retry values
        max_retries = config.get('max_retries', 3)
        if max_retries < 1:
            logger.warning("max_retries should be at least 1")
        elif max_retries > 10:
            logger.warning("max_retries > 10 may cause very long wait times on failure")

    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current configuration without sensitive information.

        Returns:
            Dictionary with configuration summary
        """
        try:
            config = self.load_config()
            return {
                'model': config.openai_model,
                'base_url': config.openai_base_url,
                'timeout': config.timeout,
                'max_retries': config.max_retries,
                'log_path': str(config.log_path),
                'auto_commit': config.auto_commit,
                'auto_push': config.auto_push,
                'configuration_sources': self._get_active_config_sources()
            }
        except Exception as e:
            return {
                'error': str(e),
                'configuration_sources': self._get_active_config_sources()
            }

    def _get_active_config_sources(self) -> List[str]:
        """
        Get list of active configuration sources.

        Returns:
            List of configuration source names
        """
        sources = []

        # Check environment variables
        env_vars = ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL']
        if any(os.environ.get(var) for var in env_vars):
            sources.append('environment')

        # Check secure storage
        try:
            if hasattr(self, '_load_from_secure_storage'):
                api_key = self._load_from_secure_storage()
                if api_key:
                    sources.append('secure_storage')
        except Exception:
            pass

        # Check configuration files
        config_type, config_file = self._find_config_files()
        if config_file:
            sources.append(f'{config_type}_file')

        return sources if sources else ['none']


def create_default_config_file(file_type: str = "aicommit") -> Path:
    """
    Create a default configuration file template.

    Args:
        file_type: Type of config file to create ('aicommit' or 'env')

    Returns:
        Path to created config file
    """
    filename = '.aicommit' if file_type == 'aicommit' else '.env'
    config_path = Path.cwd() / filename

    template_content = """# AI Commit Configuration
# Copy this file and fill in your settings

# Required settings
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo

# Optional settings
LOG_PATH=.commitLogs
AUTO_COMMIT=false
AUTO_PUSH=false
MAX_RETRIES=3
TIMEOUT=30
"""

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(template_content)

    logger.info(f"Created configuration template: {config_path}")
    return config_path
