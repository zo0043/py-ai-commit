"""
Configuration management for AI Commit.

This module handles loading, validation, and management of configuration settings.
"""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dotenv import load_dotenv

from ..exceptions import ConfigurationError
from ..security import APIKeyManager, InputValidator, mask_api_key

logger = logging.getLogger(__name__)


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
        
        Args:
            config_path: Optional path to specific config file
            
        Returns:
            Loaded and validated configuration
            
        Raises:
            ConfigurationError: If configuration cannot be loaded or is invalid
        """
        config = {}
        
        # 1. Load from environment variables (lowest priority)
        env_config = self._load_from_environment()
        if env_config:
            config.update(env_config)
            logger.info(f"Loaded configuration from environment: {', '.join(env_config.keys())}")
        
        # 2. Load from secure storage
        secure_config = self._load_from_secure_storage()
        if secure_config:
            config.update(secure_config)
            logger.info("Loaded API key from secure storage")
        
        # 3. Load from configuration files (higher priority)
        config_type, config_file = self._find_config_files(config_path)
        if config_file:
            file_config = self._load_from_file(config_type, config_file)
            if file_config:
                config.update(file_config)
                logger.info(f"Loaded configuration from {config_type} file: {config_file}")
        
        # 4. Validate we have required configuration
        if not config:
            self._show_configuration_help()
            raise ConfigurationError("No configuration found")
        
        # 5. Convert and validate configuration
        return self._create_config_object(config)
    
    def _load_from_environment(self) -> Dict[str, str]:
        """Load configuration from environment variables."""
        config = {}
        for key in self.ENV_VARS:
            value = os.getenv(key)
            if value:
                config[key] = value
        return config
    
    def _load_from_secure_storage(self) -> Dict[str, str]:
        """Load API key from secure storage."""
        try:
            api_key = self.api_key_manager.get_api_key("openai")
            if api_key:
                return {'OPENAI_API_KEY': api_key}
        except Exception as e:
            logger.debug(f"Could not load from secure storage: {e}")
        return {}
    
    def _find_config_files(self, config_path: Optional[str] = None) -> Tuple[Optional[str], Optional[Path]]:
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
                raise ConfigurationError(
                    "Found .aicommit_template file. Please configure it and rename to .aicommit"
                )
                
            current = current.parent
        
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
            if config_type in ('aicommit', 'custom'):
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
            missing_fields = [field for field in ['openai_api_key', 'openai_base_url', 'openai_model'] 
                            if field not in processed_config]
            if missing_fields:
                raise ConfigurationError(f"Missing required configuration: {', '.join(missing_fields)}")
            raise ConfigurationError(f"Invalid configuration: {e}")
    
    def _show_configuration_help(self) -> None:
        """Display helpful configuration instructions."""
        print("\n" + "="*60)
        print("❌ Configuration Required")
        print("="*60)
        print("No configuration found. You can configure ai-commit in multiple ways:")
        print("\n1. Environment Variables:")
        print("   export OPENAI_API_KEY='your-api-key'")
        print("   export OPENAI_BASE_URL='https://api.openai.com/v1'")
        print("   export OPENAI_MODEL='gpt-3.5-turbo'")
        print("\n2. Configuration File (.aicommit or .env):")
        print("   Create a file with your settings in the current directory")
        print("\n3. Secure Storage:")
        print("   Use 'ai-commit config set-key' to store API key securely")
        print("="*60)


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