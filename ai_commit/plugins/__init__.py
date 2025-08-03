"""
插件化架构核心组件

实现基于插件的架构，支持动态加载、配置和管理插件。
遵循SOLID原则，提供高内聚、低耦合的插件系统。
"""

import os
import sys
import importlib
import importlib.util
import logging
import json
import yaml
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import inspect
import traceback

from ..exceptions import PluginError, ConfigurationError
from ..security import InputValidator
from ..core.event_system import EventManager, EventType, Event
from ..config.enhanced_config import PluginConfigManager, ConfigSource
from .error_handling import PluginErrorHandler, ErrorContext, ErrorLevel, ErrorCategory, PluginPerformanceMonitor

logger = logging.getLogger(__name__)


class PluginType(Enum):
    """插件类型枚举"""
    HOOK = "hook"           # 钩子插件
    PROCESSOR = "processor" # 处理器插件
    INTEGRATION = "integration"  # 集成插件
    UI = "ui"              # UI插件
    CACHE = "cache"        # 缓存插件
    VALIDATOR = "validator" # 验证器插件


class PluginStatus(Enum):
    """插件状态枚举"""
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    homepage: str = ""
    repository: str = ""
    license: str = "MIT"


class PluginInterface(ABC):
    """插件接口基类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化插件
        
        Args:
            config: 插件配置
        """
        self.config = config or {}
        self._enabled = False
        self._initialized = False
        self.logger = logging.getLogger(f"plugin.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """获取插件元数据"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化插件
        
        Returns:
            初始化是否成功
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """清理插件资源"""
        pass
    
    def enable(self) -> bool:
        """
        启用插件
        
        Returns:
            启用是否成功
        """
        if not self._initialized:
            if not self.initialize():
                return False
        
        self._enabled = True
        self.logger.info(f"Plugin {self.metadata.name} enabled")
        return True
    
    def disable(self) -> None:
        """禁用插件"""
        self._enabled = False
        self.logger.info(f"Plugin {self.metadata.name} disabled")
    
    def is_enabled(self) -> bool:
        """检查插件是否启用"""
        return self._enabled
    
    def is_initialized(self) -> bool:
        """检查插件是否已初始化"""
        return self._initialized
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取插件配置
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """
        设置插件配置
        
        Args:
            key: 配置键
            value: 配置值
        """
        self.config[key] = value
        self.logger.debug(f"Config updated: {key} = {value}")


class HookPlugin(PluginInterface):
    """钩子插件基类"""
    
    @abstractmethod
    def execute_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行钩子
        
        Args:
            context: 钩子上下文
            
        Returns:
            执行结果
        """
        pass


class ProcessorPlugin(PluginInterface):
    """处理器插件基类"""
    
    @abstractmethod
    def process(self, data: Any) -> Any:
        """
        处理数据
        
        Args:
            data: 输入数据
            
        Returns:
            处理结果
        """
        pass


class PluginConfig:
    """插件配置管理（保持向后兼容性）"""
    
    def __init__(self, config_path: str = "plugins.yaml"):
        """
        初始化插件配置
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.enhanced_config = PluginConfigManager(config_path)
        self.config = self.enhanced_config.get_all_config()
    
    def load_config(self) -> None:
        """加载插件配置（委托给增强配置管理器）"""
        self.enhanced_config.reload_config()
        self.config = self.enhanced_config.get_all_config()
    
    def save_config(self) -> None:
        """保存插件配置（委托给增强配置管理器）"""
        self.enhanced_config.save_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'plugin_directories': ['plugins'],
            'enabled_plugins': [],
            'disabled_plugins': [],
            'plugin_configs': {},
            'auto_load': True,
            'strict_validation': True
        }
    
    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """
        获取特定插件的配置
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件配置
        """
        return self.config.get('plugin_configs', {}).get(plugin_name, {})
    
    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> None:
        """
        设置插件配置
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
        """
        if 'plugin_configs' not in self.config:
            self.config['plugin_configs'] = {}
        self.config['plugin_configs'][plugin_name] = config
        self.save_config()
    
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """
        检查插件是否启用
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            是否启用
        """
        return (
            plugin_name in self.config.get('enabled_plugins', []) and
            plugin_name not in self.config.get('disabled_plugins', [])
        )
    
    def enable_plugin(self, plugin_name: str) -> None:
        """
        启用插件
        
        Args:
            plugin_name: 插件名称
        """
        if 'enabled_plugins' not in self.config:
            self.config['enabled_plugins'] = []
        
        if plugin_name not in self.config['enabled_plugins']:
            self.config['enabled_plugins'].append(plugin_name)
        
        if 'disabled_plugins' in self.config and plugin_name in self.config['disabled_plugins']:
            self.config['disabled_plugins'].remove(plugin_name)
        
        self.save_config()
    
    def disable_plugin(self, plugin_name: str) -> None:
        """
        禁用插件
        
        Args:
            plugin_name: 插件名称
        """
        if 'disabled_plugins' not in self.config:
            self.config['disabled_plugins'] = []
        
        if plugin_name not in self.config['disabled_plugins']:
            self.config['disabled_plugins'].append(plugin_name)
        
        if 'enabled_plugins' in self.config and plugin_name in self.config['enabled_plugins']:
            self.config['enabled_plugins'].remove(plugin_name)
        
        self.save_config()
    
    def get_config_source(self, key: str) -> Optional[str]:
        """
        获取配置来源
        
        Args:
            key: 配置键
            
        Returns:
            配置来源
        """
        source = self.enhanced_config.get_config_source(key)
        return source.value if source else None
    
    def get_config_info(self) -> Dict[str, Dict[str, Any]]:
        """
        获取配置详细信息
        
        Returns:
            配置信息字典
        """
        return self.enhanced_config.get_config_info()
    
    def register_plugin_schema(self, plugin_name: str, schema: Dict[str, Any]) -> None:
        """
        注册插件配置模式
        
        Args:
            plugin_name: 插件名称
            schema: 配置模式
        """
        self.enhanced_config.register_plugin_schema(plugin_name, schema)
    
    def validate_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """
        验证插件配置
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
            
        Returns:
            验证是否通过
        """
        return self.enhanced_config.validate_plugin_config(plugin_name, config)
    
    def merge_config(self, new_config: Dict[str, Any]) -> None:
        """
        合并配置
        
        Args:
            new_config: 新配置
        """
        self.enhanced_config.merge_config(new_config)
        self.config = self.enhanced_config.get_all_config()
    
    def reset_to_defaults(self) -> None:
        """重置为默认配置"""
        self.enhanced_config.reset_to_defaults()
        self.config = self.enhanced_config.get_all_config()


class PluginManager:
    """插件管理器"""
    
    def __init__(self, config_path: str = "plugins.yaml"):
        """
        初始化插件管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = PluginConfig(config_path)
        self.plugins: Dict[str, PluginInterface] = {}
        self.plugin_metadata: Dict[str, PluginMetadata] = {}
        self.plugin_status: Dict[str, PluginStatus] = {}
        self.plugin_types: Dict[PluginType, List[str]] = {}
        self.event_manager: Optional[EventManager] = None
        self.validator = InputValidator()
        self.performance_stats = {
            'plugins_loaded': 0,
            'plugins_enabled': 0,
            'plugins_failed': 0,
            'load_time': 0,
            'execution_time': 0
        }
        
        # 初始化错误处理和性能监控
        self.error_handler = PluginErrorHandler()
        self.performance_monitor = PluginPerformanceMonitor()
        
        # 初始化插件类型索引
        for plugin_type in PluginType:
            self.plugin_types[plugin_type] = []
        
        logger.info("Plugin manager initialized")
    
    def set_event_manager(self, event_manager: EventManager) -> None:
        """
        设置事件管理器
        
        Args:
            event_manager: 事件管理器
        """
        self.event_manager = event_manager
        logger.info("Event manager set for plugin system")
    
    def discover_plugins(self) -> List[str]:
        """
        发现插件
        
        Returns:
            发现的插件名称列表
        """
        discovered = []
        plugin_dirs = self.config.config.get('plugin_directories', ['plugins'])
        
        for plugin_dir in plugin_dirs:
            plugin_path = Path(plugin_dir)
            if not plugin_path.exists():
                continue
            
            # 扫描Python文件
            for py_file in plugin_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                
                plugin_name = py_file.stem
                if plugin_name not in discovered:
                    discovered.append(plugin_name)
            
            # 扫描插件目录
            for plugin_dir_path in plugin_path.iterdir():
                if not plugin_dir_path.is_dir() or plugin_dir_path.name.startswith("_"):
                    continue
                
                plugin_name = plugin_dir_path.name
                if plugin_name not in discovered:
                    discovered.append(plugin_name)
        
        logger.info(f"Discovered {len(discovered)} plugins: {discovered}")
        return discovered
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        加载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            加载是否成功
        """
        if plugin_name in self.plugins:
            logger.warning(f"Plugin {plugin_name} already loaded")
            return True
        
        # 开始性能监控
        timer_id = self.performance_monitor.start_plugin_load_timer(plugin_name)
        
        try:
            # 查找插件文件
            plugin_class = self._find_plugin_class(plugin_name)
            if not plugin_class:
                error_context = ErrorContext(
                    plugin_name=plugin_name,
                    operation="load_plugin",
                    additional_info={"step": "find_plugin_class"}
                )
                self.error_handler.handle_error(
                    Exception(f"Plugin class not found: {plugin_name}"),
                    error_context,
                    ErrorLevel.ERROR,
                    ErrorCategory.EXECUTION
                )
                return False
            
            # 创建插件实例
            plugin_config = self.config.get_plugin_config(plugin_name)
            plugin_instance = plugin_class(plugin_config)
            
            # 验证插件
            if not self._validate_plugin(plugin_instance):
                error_context = ErrorContext(
                    plugin_name=plugin_name,
                    operation="load_plugin",
                    additional_info={"step": "validate_plugin"}
                )
                self.error_handler.handle_error(
                    Exception(f"Plugin validation failed: {plugin_name}"),
                    error_context,
                    ErrorLevel.ERROR,
                    ErrorCategory.VALIDATION
                )
                return False
            
            # 存储插件
            self.plugins[plugin_name] = plugin_instance
            self.plugin_metadata[plugin_name] = plugin_instance.metadata
            self.plugin_status[plugin_name] = PluginStatus.LOADED
            
            # 按类型索引
            plugin_type = plugin_instance.metadata.plugin_type
            if plugin_name not in self.plugin_types[plugin_type]:
                self.plugin_types[plugin_type].append(plugin_name)
            
            # 结束性能监控
            self.performance_monitor.end_plugin_load_timer(plugin_name, timer_id)
            
            # 记录成功加载
            self.performance_stats['plugins_loaded'] += 1
            
            logger.info(f"Plugin loaded successfully: {plugin_name}")
            
            # 发布插件加载事件
            if self.event_manager:
                self.event_manager.publish_user_action(
                    "plugin_loaded",
                    {"plugin_name": plugin_name, "plugin_type": plugin_type.value}
                )
            
            return True
            
        except Exception as e:
            # 结束性能监控
            self.performance_monitor.end_plugin_load_timer(plugin_name, timer_id)
            
            # 处理错误
            error_context = ErrorContext(
                plugin_name=plugin_name,
                operation="load_plugin",
                additional_info={"step": "general_load"}
            )
            self.error_handler.handle_error(e, error_context)
            
            self.plugin_status[plugin_name] = PluginStatus.ERROR
            self.performance_stats['plugins_failed'] += 1
            
            return False
    
    def _find_plugin_class(self, plugin_name: str) -> Optional[Type[PluginInterface]]:
        """
        查找插件类
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件类或None
        """
        plugin_dirs = self.config.config.get('plugin_directories', ['plugins'])
        
        for plugin_dir in plugin_dirs:
            plugin_path = Path(plugin_dir)
            if not plugin_path.exists():
                continue
            
            # 尝试加载Python文件
            py_file = plugin_path / f"{plugin_name}.py"
            if py_file.exists():
                return self._load_plugin_from_file(py_file, plugin_name)
            
            # 尝试加载插件目录
            plugin_dir_path = plugin_path / plugin_name
            if plugin_dir_path.exists() and plugin_dir_path.is_dir():
                # 查找主文件
                main_file = plugin_dir_path / "__init__.py"
                if main_file.exists():
                    return self._load_plugin_from_file(main_file, plugin_name)
                
                # 查找plugin.py
                plugin_file = plugin_dir_path / "plugin.py"
                if plugin_file.exists():
                    return self._load_plugin_from_file(plugin_file, plugin_name)
        
        return None
    
    def _load_plugin_from_file(self, file_path: Path, plugin_name: str) -> Optional[Type[PluginInterface]]:
        """
        从文件加载插件类
        
        Args:
            file_path: 文件路径
            plugin_name: 插件名称
            
        Returns:
            插件类或None
        """
        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_name}", file_path)
            if not spec or not spec.loader:
                logger.error(f"Cannot create module spec for {plugin_name}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类 - 首先尝试PluginInterface子类
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, PluginInterface) and 
                    obj != PluginInterface and
                    not inspect.isabstract(obj)):
                    return obj
            
            # 如果没有找到，尝试查找具有特定模式的类
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    not inspect.isabstract(obj) and
                    name.endswith(('Plugin', 'Hook', 'Processor', 'Integration'))):
                    
                    # 检查是否有必要的方法
                    if hasattr(obj, 'metadata') and hasattr(obj, 'initialize'):
                        # 尝试创建一个适配器类
                        return self._create_plugin_adapter(obj, name)
            
            logger.error(f"No plugin class found in {file_path}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load plugin from {file_path}: {e}")
            return None
    
    def _create_plugin_adapter(self, plugin_class: Type, class_name: str) -> Type[PluginInterface]:
        """
        为独立插件创建适配器
        
        Args:
            plugin_class: 原始插件类
            class_name: 类名
            
        Returns:
            适配后的插件类
        """
        class PluginAdapter(PluginInterface):
            def __init__(self, config=None):
                self._plugin = plugin_class(config)
                self.config = config or {}
                self._enabled = False
                self._initialized = False
                self.logger = logging.getLogger(f"plugin.{class_name}")
            
            @property
            def metadata(self):
                # 获取原始插件的元数据
                if hasattr(self._plugin, 'metadata'):
                    return self._plugin.metadata
                else:
                    # 创建默认元数据
                    return PluginMetadata(
                        name=class_name.lower(),
                        version="1.0.0",
                        description=f"Auto-generated adapter for {class_name}",
                        author="Unknown",
                        plugin_type=PluginType.HOOK
                    )
            
            def initialize(self):
                try:
                    if hasattr(self._plugin, 'initialize'):
                        result = self._plugin.initialize()
                    else:
                        result = True
                    
                    self._initialized = result
                    return result
                except Exception as e:
                    logger.error(f"Failed to initialize plugin adapter: {e}")
                    return False
            
            def cleanup(self):
                try:
                    if hasattr(self._plugin, 'cleanup'):
                        self._plugin.cleanup()
                except Exception as e:
                    logger.error(f"Error during plugin cleanup: {e}")
            
            def enable(self):
                if not self._initialized:
                    if not self.initialize():
                        return False
                
                if hasattr(self._plugin, 'enable'):
                    result = self._plugin.enable()
                else:
                    result = True
                
                self._enabled = result
                return result
            
            def disable(self):
                if hasattr(self._plugin, 'disable'):
                    self._plugin.disable()
                self._enabled = False
            
            def is_enabled(self):
                return self._enabled
            
            def is_initialized(self):
                return self._initialized
            
            def get_config(self, key, default=None):
                if hasattr(self._plugin, 'get_config'):
                    return self._plugin.get_config(key, default)
                return self.config.get(key, default)
            
            def set_config(self, key, value):
                self.config[key] = value
                if hasattr(self._plugin, 'set_config'):
                    self._plugin.set_config(key, value)
            
            # 特殊方法支持
            def __getattr__(self, name):
                return getattr(self._plugin, name)
        
        return PluginAdapter
    
    def _validate_plugin(self, plugin: PluginInterface) -> bool:
        """
        验证插件
        
        Args:
            plugin: 插件实例
            
        Returns:
            验证是否通过
        """
        try:
            # 检查元数据
            metadata = plugin.metadata
            if not metadata.name or not metadata.version:
                logger.error("Plugin metadata missing required fields")
                return False
            
            # 检查依赖
            for dep in metadata.dependencies:
                if dep not in self.plugins:
                    logger.error(f"Missing dependency: {dep}")
                    return False
            
            # 检查权限
            for permission in metadata.permissions:
                if not self._check_permission(permission):
                    logger.error(f"Permission denied: {permission}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Plugin validation error: {e}")
            return False
    
    def _check_permission(self, permission: str) -> bool:
        """
        检查权限
        
        Args:
            permission: 权限字符串
            
        Returns:
            是否有权限
        """
        # 这里可以实现具体的权限检查逻辑
        # 目前默认允许所有权限
        return True
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """
        启用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            启用是否成功
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin not loaded: {plugin_name}")
            return False
        
        plugin = self.plugins[plugin_name]
        if plugin.enable():
            self.plugin_status[plugin_name] = PluginStatus.ENABLED
            self.config.enable_plugin(plugin_name)
            
            # 发布插件启用事件
            if self.event_manager:
                self.event_manager.publish_user_action(
                    "plugin_enabled",
                    {"plugin_name": plugin_name}
                )
            
            return True
        
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            禁用是否成功
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin not loaded: {plugin_name}")
            return False
        
        plugin = self.plugins[plugin_name]
        plugin.disable()
        self.plugin_status[plugin_name] = PluginStatus.DISABLED
        self.config.disable_plugin(plugin_name)
        
        # 发布插件禁用事件
        if self.event_manager:
            self.event_manager.publish_user_action(
                "plugin_disabled",
                {"plugin_name": plugin_name}
            )
        
        return True
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            卸载是否成功
        """
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin not loaded: {plugin_name}")
            return True
        
        plugin = self.plugins[plugin_name]
        
        # 禁用插件
        if plugin.is_enabled():
            plugin.disable()
        
        # 清理插件
        try:
            plugin.cleanup()
        except Exception as e:
            logger.error(f"Error during plugin cleanup: {e}")
        
        # 从管理器中移除
        del self.plugins[plugin_name]
        del self.plugin_metadata[plugin_name]
        del self.plugin_status[plugin_name]
        
        # 从类型索引中移除
        plugin_type = plugin.metadata.plugin_type
        type_key = plugin_type if isinstance(plugin_type, PluginType) else None
        
        # 如果plugin_type是字符串，查找对应的枚举
        if type_key is None:
            for pt in PluginType:
                if pt.value == plugin_type:
                    type_key = pt
                    break
        
        if type_key and plugin_name in self.plugin_types[type_key]:
            self.plugin_types[type_key].remove(plugin_name)
        
        logger.info(f"Plugin unloaded: {plugin_name}")
        
        # 发布插件卸载事件
        if self.event_manager:
            self.event_manager.publish_user_action(
                "plugin_unloaded",
                {"plugin_name": plugin_name}
            )
        
        return True
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """
        获取插件实例
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            插件实例或None
        """
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginInterface]:
        """
        根据类型获取插件
        
        Args:
            plugin_type: 插件类型
            
        Returns:
            插件列表
        """
        return [self.plugins[name] for name in self.plugin_types[plugin_type]]
    
    def get_enabled_plugins(self) -> List[PluginInterface]:
        """
        获取已启用的插件
        
        Returns:
            已启用的插件列表
        """
        return [
            plugin for name, plugin in self.plugins.items()
            if self.plugin_status[name] == PluginStatus.ENABLED
        ]
    
    def execute_hook(self, hook_name: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行钩子
        
        Args:
            hook_name: 钩子名称
            context: 上下文数据
            
        Returns:
            执行结果
        """
        if context is None:
            context = {}
        
        result = context.copy()
        
        # 获取所有钩子插件
        hook_plugins = self.get_plugins_by_type(PluginType.HOOK)
        
        for plugin in hook_plugins:
            if plugin.is_enabled() and isinstance(plugin, HookPlugin):
                start_time = time.time()
                success = False
                
                try:
                    hook_result = plugin.execute_hook(result)
                    if hook_result:
                        result.update(hook_result)
                    success = True
                    
                except Exception as e:
                    # 处理错误
                    error_context = ErrorContext(
                        plugin_name=plugin.metadata.name,
                        operation=f"execute_hook:{hook_name}",
                        additional_info={"hook_name": hook_name, "context": context}
                    )
                    self.error_handler.handle_error(e, error_context)
                    
                finally:
                    # 记录性能
                    duration = time.time() - start_time
                    self.performance_monitor.record_plugin_execution(
                        plugin.metadata.name,
                        f"hook:{hook_name}",
                        duration,
                        success
                    )
        
        return result
    
    def process_data(self, data: Any, processor_type: PluginType = PluginType.PROCESSOR) -> Any:
        """
        处理数据
        
        Args:
            data: 输入数据
            processor_type: 处理器类型
            
        Returns:
            处理结果
        """
        result = data
        
        # 获取所有处理器插件
        processor_plugins = self.get_plugins_by_type(processor_type)
        
        for plugin in processor_plugins:
            if plugin.is_enabled() and isinstance(plugin, ProcessorPlugin):
                start_time = time.time()
                success = False
                
                try:
                    result = plugin.process(result)
                    success = True
                    
                except Exception as e:
                    # 处理错误
                    error_context = ErrorContext(
                        plugin_name=plugin.metadata.name,
                        operation=f"process_data:{processor_type.value}",
                        additional_info={"processor_type": processor_type.value}
                    )
                    self.error_handler.handle_error(e, error_context)
                    
                finally:
                    # 记录性能
                    duration = time.time() - start_time
                    self.performance_monitor.record_plugin_execution(
                        plugin.metadata.name,
                        f"process:{processor_type.value}",
                        duration,
                        success
                    )
        
        return result
    
    def load_all_plugins(self) -> None:
        """加载所有插件"""
        discovered = self.discover_plugins()
        
        for plugin_name in discovered:
            if self.config.is_plugin_enabled(plugin_name):
                self.load_plugin(plugin_name)
    
    def get_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取插件状态
        
        Returns:
            插件状态信息
        """
        status = {}
        
        for plugin_name, plugin in self.plugins.items():
            # 处理plugin_type，可能是枚举或字符串
            plugin_type = plugin.metadata.plugin_type
            type_value = plugin_type.value if hasattr(plugin_type, 'value') else plugin_type
            
            status[plugin_name] = {
                'status': self.plugin_status[plugin_name].value,
                'metadata': {
                    'name': plugin.metadata.name,
                    'version': plugin.metadata.version,
                    'description': plugin.metadata.description,
                    'type': type_value,
                    'author': plugin.metadata.author
                },
                'enabled': plugin.is_enabled(),
                'initialized': plugin.is_initialized()
            }
        
        return status
    
    def cleanup(self) -> None:
        """清理所有插件"""
        for plugin_name in list(self.plugins.keys()):
            self.unload_plugin(plugin_name)
        
        logger.info("Plugin manager cleaned up")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Returns:
            性能统计信息
        """
        return self.performance_stats.copy()
    
    def reset_performance_stats(self) -> None:
        """重置性能统计"""
        self.performance_stats = {
            'plugins_loaded': 0,
            'plugins_enabled': 0,
            'plugins_failed': 0,
            'load_time': 0,
            'execution_time': 0
        }
    
    def get_plugin_dependencies(self, plugin_name: str) -> List[str]:
        """
        获取插件的依赖关系
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            依赖列表
        """
        if plugin_name not in self.plugin_metadata:
            return []
        
        return self.plugin_metadata[plugin_name].dependencies
    
    def check_dependency_conflicts(self) -> List[Dict[str, Any]]:
        """
        检查依赖冲突
        
        Returns:
            冲突列表
        """
        conflicts = []
        
        for plugin_name, metadata in self.plugin_metadata.items():
            for dep in metadata.dependencies:
                if dep not in self.plugins:
                    conflicts.append({
                        'type': 'missing_dependency',
                        'plugin': plugin_name,
                        'dependency': dep
                    })
        
        return conflicts
    
    def optimize_plugin_loading(self) -> None:
        """优化插件加载顺序"""
        # 根据依赖关系重新排序插件
        loaded_order = list(self.plugins.keys())
        optimized_order = self._resolve_dependencies(loaded_order)
        
        # 重新加载插件以优化顺序
        for plugin_name in optimized_order:
            if plugin_name in self.plugins and self.plugins[plugin_name].is_enabled():
                self.disable_plugin(plugin_name)
                self.enable_plugin(plugin_name)
    
    def _resolve_dependencies(self, plugin_names: List[str]) -> List[str]:
        """
        解析依赖关系
        
        Args:
            plugin_names: 插件名称列表
            
        Returns:
            解析后的插件顺序
        """
        resolved = []
        unresolved = set(plugin_names)
        
        while unresolved:
            # 找到没有未解析依赖的插件
            ready = []
            for plugin_name in unresolved:
                deps = self.get_plugin_dependencies(plugin_name)
                if all(dep in resolved for dep in deps):
                    ready.append(plugin_name)
            
            if not ready:
                # 循环依赖
                break
            
            resolved.extend(ready)
            unresolved -= set(ready)
        
        return resolved
    
    def get_plugin_health(self, plugin_name: str) -> Dict[str, Any]:
        """
        获取插件健康状态
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            健康状态信息
        """
        if plugin_name not in self.plugins:
            return {'status': 'not_loaded'}
        
        plugin = self.plugins[plugin_name]
        status = self.plugin_status[plugin_name]
        
        health = {
            'name': plugin_name,
            'status': status.value,
            'enabled': plugin.is_enabled(),
            'initialized': plugin.is_initialized(),
            'dependencies': self.get_plugin_dependencies(plugin_name),
            'dependency_status': 'resolved'
        }
        
        # 检查依赖状态
        for dep in health['dependencies']:
            if dep not in self.plugins:
                health['dependency_status'] = 'missing'
                break
        
        return health
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        获取系统健康状态
        
        Returns:
            系统健康状态
        """
        return {
            'total_plugins': len(self.plugins),
            'enabled_plugins': len([p for p in self.plugins.values() if p.is_enabled()]),
            'disabled_plugins': len([p for p in self.plugins.values() if not p.is_enabled()]),
            'failed_plugins': len([s for s in self.plugin_status.values() if s == PluginStatus.ERROR]),
            'dependency_conflicts': self.check_dependency_conflicts(),
            'performance_stats': self.get_performance_stats()
        }


# 全局插件管理器实例
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """获取全局插件管理器实例"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def cleanup_plugin_system() -> None:
    """清理插件系统"""
    global _plugin_manager
    if _plugin_manager:
        _plugin_manager.cleanup()
        _plugin_manager = None