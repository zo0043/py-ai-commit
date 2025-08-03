"""
增强的插件配置管理模块

提供灵活、类型安全的插件配置管理，支持环境变量、配置文件和运行时配置。
"""

import os
import json
import yaml
import logging
from typing import Dict, Any, Optional, Union, List, Callable
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum

from ..exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class ConfigSource(Enum):
    """配置来源枚举"""
    DEFAULT = "default"
    CONFIG_FILE = "config_file"
    ENVIRONMENT = "environment"
    RUNTIME = "runtime"


@dataclass
class ConfigValue:
    """配置值包装器"""
    value: Any
    source: ConfigSource
    validator: Optional[Callable[[Any], bool]] = None
    description: str = ""
    
    def validate(self) -> bool:
        """验证配置值"""
        if self.validator:
            return self.validator(self.value)
        return True


class PluginConfigManager:
    """增强的插件配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path) if config_path else Path("plugins.yaml")
        self.config_values: Dict[str, ConfigValue] = {}
        self.schema_validators: Dict[str, Dict[str, Callable]] = {}
        self._load_default_config()
        self._load_config_file()
        self._load_environment_variables()
    
    def _load_default_config(self) -> None:
        """加载默认配置"""
        default_config = {
            'plugin_directories': ['plugins'],
            'enabled_plugins': [],
            'disabled_plugins': [],
            'plugin_configs': {},
            'auto_load': True,
            'strict_validation': True,
            'log_level': 'INFO',
            'max_plugin_instances': 100,
            'plugin_timeout': 30,
            'cache_enabled': True,
            'cache_ttl': 3600
        }
        
        for key, value in default_config.items():
            self.config_values[key] = ConfigValue(
                value=value,
                source=ConfigSource.DEFAULT,
                description=f"Default {key}"
            )
    
    def _load_config_file(self) -> None:
        """加载配置文件"""
        if not self.config_path.exists():
            logger.info(f"Config file not found: {self.config_path}")
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                    config_data = yaml.safe_load(f) or {}
                else:
                    config_data = json.load(f) or {}
            
            for key, value in config_data.items():
                self.config_values[key] = ConfigValue(
                    value=value,
                    source=ConfigSource.CONFIG_FILE,
                    description=f"Config file {key}"
                )
            
            logger.info(f"Loaded config from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load config file {self.config_path}: {e}")
            raise ConfigurationError(f"Failed to load config file: {e}")
    
    def _load_environment_variables(self) -> None:
        """加载环境变量"""
        env_mapping = {
            'AI_COMMIT_PLUGIN_DIRS': 'plugin_directories',
            'AI_COMMIT_ENABLED_PLUGINS': 'enabled_plugins',
            'AI_COMMIT_DISABLED_PLUGINS': 'disabled_plugins',
            'AI_COMMIT_AUTO_LOAD': 'auto_load',
            'AI_COMMIT_STRICT_VALIDATION': 'strict_validation',
            'AI_COMMIT_LOG_LEVEL': 'log_level',
            'AI_COMMIT_PLUGIN_TIMEOUT': 'plugin_timeout',
            'AI_COMMIT_CACHE_ENABLED': 'cache_enabled',
            'AI_COMMIT_CACHE_TTL': 'cache_ttl'
        }
        
        for env_var, config_key in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # 转换环境变量值类型
                converted_value = self._convert_env_value(env_value, config_key)
                self.config_values[config_key] = ConfigValue(
                    value=converted_value,
                    source=ConfigSource.ENVIRONMENT,
                    description=f"Environment variable {env_var}"
                )
    
    def _convert_env_value(self, value: str, config_key: str) -> Any:
        """转换环境变量值类型"""
        # 根据配置键确定类型
        type_hints = {
            'plugin_directories': lambda x: x.split(','),
            'enabled_plugins': lambda x: x.split(','),
            'disabled_plugins': lambda x: x.split(','),
            'auto_load': lambda x: x.lower() in ['true', '1', 'yes'],
            'strict_validation': lambda x: x.lower() in ['true', '1', 'yes'],
            'log_level': lambda x: x.upper(),
            'max_plugin_instances': int,
            'plugin_timeout': int,
            'cache_enabled': lambda x: x.lower() in ['true', '1', 'yes'],
            'cache_ttl': int
        }
        
        converter = type_hints.get(config_key, lambda x: x)
        try:
            return converter(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to convert env value '{value}' for {config_key}: {e}")
            return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        config_value = self.config_values.get(key)
        if config_value is None:
            return default
        
        if not config_value.validate():
            logger.warning(f"Config validation failed for {key}: {config_value.value}")
            return default
        
        return config_value.value
    
    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.RUNTIME) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            source: 配置来源
        """
        self.config_values[key] = ConfigValue(
            value=value,
            source=source,
            description=f"Runtime {key}"
        )
        
        logger.debug(f"Config updated: {key} = {value} (source: {source.value})")
    
    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """
        获取插件配置
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件配置字典
        """
        plugin_configs = self.get('plugin_configs', {})
        return plugin_configs.get(plugin_name, {})
    
    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> None:
        """
        设置插件配置
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
        """
        plugin_configs = self.get('plugin_configs', {})
        plugin_configs[plugin_name] = config
        self.set('plugin_configs', plugin_configs)
    
    def register_plugin_schema(self, plugin_name: str, schema: Dict[str, Any]) -> None:
        """
        注册插件配置模式
        
        Args:
            plugin_name: 插件名称
            schema: 配置模式
        """
        validators = {}
        
        for field_name, field_config in schema.items():
            field_type = field_config.get('type', 'string')
            default_value = field_config.get('default')
            
            # 创建验证器
            def create_validator(field_type, default_value):
                def validator(value):
                    if value is None and default_value is None:
                        return True
                    
                    try:
                        if field_type == 'boolean':
                            return isinstance(value, bool) or (
                                isinstance(value, str) and 
                                value.lower() in ['true', 'false', '1', '0']
                            )
                        elif field_type == 'integer':
                            return isinstance(value, int)
                        elif field_type == 'number':
                            return isinstance(value, (int, float))
                        elif field_type == 'array':
                            return isinstance(value, list)
                        elif field_type == 'string':
                            return isinstance(value, str)
                        return True
                    except Exception:
                        return False
                return validator
            
            validators[field_name] = create_validator(field_type, default_value)
        
        self.schema_validators[plugin_name] = validators
    
    def validate_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        验证插件配置
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
            
        Returns:
            验证是否通过
        """
        if plugin_name not in self.schema_validators:
            logger.warning(f"No schema registered for plugin {plugin_name}")
            return True
        
        validators = self.schema_validators[plugin_name]
        
        for field_name, validator in validators.items():
            if field_name in config:
                if not validator(config[field_name]):
                    logger.error(f"Validation failed for {plugin_name}.{field_name}: {config[field_name]}")
                    return False
        
        return True
    
    def get_config_source(self, key: str) -> Optional[ConfigSource]:
        """
        获取配置来源
        
        Args:
            key: 配置键
            
        Returns:
            配置来源
        """
        config_value = self.config_values.get(key)
        return config_value.source if config_value else None
    
    def get_config_with_source(self, key: str) -> Dict[str, Any]:
        """
        获取配置值和来源信息
        
        Args:
            key: 配置键
            
        Returns:
            包含值和来源信息的字典
        """
        config_value = self.config_values.get(key)
        if config_value is None:
            return {'value': None, 'source': None, 'valid': False}
        
        return {
            'value': config_value.value,
            'source': config_value.source.value,
            'valid': config_value.validate(),
            'description': config_value.description
        }
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            # 只保存非默认的运行时配置
            runtime_config = {}
            for key, config_value in self.config_values.items():
                if config_value.source in [ConfigSource.CONFIG_FILE, ConfigSource.RUNTIME]:
                    runtime_config[key] = config_value.value
            
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(runtime_config, f, default_flow_style=False, indent=2)
                else:
                    json.dump(runtime_config, f, indent=2)
            
            logger.info(f"Config saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise ConfigurationError(f"Failed to save config: {e}")
    
    def reload_config(self) -> None:
        """重新加载配置"""
        logger.info("Reloading configuration")
        
        # 保留运行时配置
        runtime_config = {}
        for key, config_value in self.config_values.items():
            if config_value.source == ConfigSource.RUNTIME:
                runtime_config[key] = config_value.value
        
        # 清空并重新加载
        self.config_values.clear()
        self._load_default_config()
        self._load_config_file()
        self._load_environment_variables()
        
        # 恢复运行时配置
        for key, value in runtime_config.items():
            self.set(key, value, ConfigSource.RUNTIME)
    
    def get_all_config(self) -> Dict[str, Any]:
        """
        获取所有配置
        
        Returns:
            所有配置的字典
        """
        return {key: config_value.value for key, config_value in self.config_values.items()}
    
    def get_config_info(self) -> Dict[str, Dict[str, Any]]:
        """
        获取配置详细信息
        
        Returns:
            包含详细配置信息的字典
        """
        info = {}
        for key, config_value in self.config_values.items():
            info[key] = {
                'value': config_value.value,
                'source': config_value.source.value,
                'valid': config_value.validate(),
                'description': config_value.description
            }
        return info
    
    def reset_to_defaults(self) -> None:
        """重置为默认配置"""
        logger.info("Resetting configuration to defaults")
        self.config_values.clear()
        self._load_default_config()
    
    def merge_config(self, new_config: Dict[str, Any], source: ConfigSource = ConfigSource.RUNTIME) -> None:
        """
        合并配置
        
        Args:
            new_config: 新配置
            source: 配置来源
        """
        for key, value in new_config.items():
            self.set(key, value, source)
    
    def export_config(self, format: str = 'yaml') -> str:
        """
        导出配置
        
        Args:
            format: 导出格式 ('yaml' 或 'json')
            
        Returns:
            配置字符串
        """
        config_data = self.get_all_config()
        
        if format.lower() == 'yaml':
            return yaml.dump(config_data, default_flow_style=False, indent=2)
        elif format.lower() == 'json':
            return json.dumps(config_data, indent=2)
        else:
            raise ConfigurationError(f"Unsupported export format: {format}")


# 全局配置管理器实例
_config_manager: Optional[PluginConfigManager] = None


def get_config_manager() -> PluginConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = PluginConfigManager()
    return _config_manager


def cleanup_config_system() -> None:
    """清理配置系统"""
    global _config_manager
    _config_manager = None