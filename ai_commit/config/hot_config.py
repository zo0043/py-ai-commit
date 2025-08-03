"""
配置热更新机制

实现配置文件的动态监听和热更新功能，无需重启应用即可更新配置。
"""

import os
import time
import logging
import asyncio
import threading
from typing import Dict, Any, Callable, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import yaml
import json

logger = logging.getLogger(__name__)


@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    config_path: str
    change_type: str  # 'created', 'modified', 'deleted'
    timestamp: float
    old_config: Optional[Dict[str, Any]] = None
    new_config: Optional[Dict[str, Any]] = None


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变更处理器"""
    
    def __init__(self, config_manager: 'HotConfigManager'):
        self.config_manager = config_manager
        self.last_modified = 0
        self.debounce_delay = 1.0  # 防抖延迟（秒）
    
    def on_modified(self, event):
        """处理文件修改事件"""
        if event.is_directory:
            return
        
        if event.src_path == self.config_manager.config_path:
            current_time = time.time()
            
            # 防抖处理
            if current_time - self.last_modified < self.debounce_delay:
                return
            
            self.last_modified = current_time
            logger.info(f"Config file modified: {event.src_path}")
            
            # 在新线程中处理配置更新
            threading.Thread(
                target=self.config_manager._handle_config_change,
                args=('modified', event.src_path),
                daemon=True
            ).start()
    
    def on_created(self, event):
        """处理文件创建事件"""
        if event.is_directory:
            return
        
        if event.src_path == self.config_manager.config_path:
            logger.info(f"Config file created: {event.src_path}")
            threading.Thread(
                target=self.config_manager._handle_config_change,
                args=('created', event.src_path),
                daemon=True
            ).start()
    
    def on_deleted(self, event):
        """处理文件删除事件"""
        if event.is_directory:
            return
        
        if event.src_path == self.config_manager.config_path:
            logger.info(f"Config file deleted: {event.src_path}")
            threading.Thread(
                target=self.config_manager._handle_config_change,
                args=('deleted', event.src_path),
                daemon=True
            ).start()


class HotConfigManager:
    """热配置管理器"""
    
    def __init__(self, config_path: str):
        """
        初始化热配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path).absolute()
        self.config: Dict[str, Any] = {}
        self.last_loaded = 0
        self.observers: List[Observer] = []
        self.change_listeners: List[Callable[[ConfigChangeEvent], None]] = []
        self.lock = threading.RLock()
        self.watching = False
        
        # 加载初始配置
        self.load_config()
        
        logger.info(f"Hot config manager initialized for {self.config_path}")
    
    def load_config(self, force: bool = False) -> Dict[str, Any]:
        """
        加载配置文件
        
        Args:
            force: 是否强制重新加载
            
        Returns:
            配置数据
        """
        if not force and self.config and time.time() - self.last_loaded < 5:
            return self.config
        
        with self.lock:
            try:
                if not self.config_path.exists():
                    logger.warning(f"Config file not found: {self.config_path}")
                    self.config = {}
                    return self.config
                
                # 读取配置文件
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                        new_config = yaml.safe_load(f) or {}
                    else:
                        new_config = json.load(f) or {}
                
                # 检查配置是否真的发生了变化
                if new_config != self.config:
                    old_config = self.config.copy()
                    self.config = new_config
                    self.last_loaded = time.time()
                    
                    # 触发配置变更事件
                    self._notify_listeners(ConfigChangeEvent(
                        config_path=str(self.config_path),
                        change_type='loaded',
                        timestamp=time.time(),
                        old_config=old_config,
                        new_config=new_config.copy()
                    ))
                    
                    logger.info("Configuration reloaded successfully")
                else:
                    logger.debug("Configuration unchanged")
                
                return self.config.copy()
                
            except Exception as e:
                logger.error(f"Failed to load config file {self.config_path}: {e}")
                return self.config.copy()
    
    def start_watching(self) -> bool:
        """
        开始监听配置文件变化
        
        Returns:
            是否成功启动监听
        """
        if self.watching:
            logger.warning("Config file watching already started")
            return True
        
        try:
            # 确保配置文件存在
            if not self.config_path.exists():
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                self.config_path.touch()
                logger.info(f"Created config file: {self.config_path}")
            
            # 创建文件系统观察器
            event_handler = ConfigFileHandler(self)
            observer = Observer()
            observer.schedule(
                event_handler,
                str(self.config_path.parent),
                recursive=False
            )
            
            observer.start()
            self.observers.append(observer)
            self.watching = True
            
            logger.info(f"Started watching config file: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start config file watching: {e}")
            return False
    
    def stop_watching(self) -> None:
        """停止监听配置文件变化"""
        if not self.watching:
            return
        
        try:
            # 停止所有观察器
            for observer in self.observers:
                observer.stop()
                observer.join()
            
            self.observers.clear()
            self.watching = False
            
            logger.info("Stopped watching config file")
            
        except Exception as e:
            logger.error(f"Failed to stop config file watching: {e}")
    
    def add_change_listener(self, listener: Callable[[ConfigChangeEvent], None]) -> None:
        """
        添加配置变更监听器
        
        Args:
            listener: 监听器函数
        """
        self.change_listeners.append(listener)
        logger.debug(f"Added config change listener: {listener}")
    
    def remove_change_listener(self, listener: Callable[[ConfigChangeEvent], None]) -> None:
        """
        移除配置变更监听器
        
        Args:
            listener: 监听器函数
        """
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)
            logger.debug(f"Removed config change listener: {listener}")
    
    def _notify_listeners(self, event: ConfigChangeEvent) -> None:
        """
        通知所有监听器
        
        Args:
            event: 配置变更事件
        """
        for listener in self.change_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error in config change listener: {e}")
    
    def _handle_config_change(self, change_type: str, file_path: str) -> None:
        """
        处理配置变更
        
        Args:
            change_type: 变更类型
            file_path: 文件路径
        """
        try:
            old_config = self.config.copy()
            
            if change_type == 'deleted':
                # 文件被删除，使用默认配置
                new_config = {}
                self.config = new_config
            else:
                # 重新加载配置
                new_config = self.load_config(force=True)
                new_config = new_config.copy()
            
            # 创建变更事件
            event = ConfigChangeEvent(
                config_path=file_path,
                change_type=change_type,
                timestamp=time.time(),
                old_config=old_config if old_config != new_config else None,
                new_config=new_config if old_config != new_config else None
            )
            
            # 通知监听器
            self._notify_listeners(event)
            
        except Exception as e:
            logger.error(f"Error handling config change: {e}")
    
    def get_config(self, key: str = None, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键（None表示获取整个配置）
            default: 默认值
            
        Returns:
            配置值
        """
        if key is None:
            return self.config.copy()
        
        # 支持嵌套键，如 'plugins.enabled_plugins'
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set_config(self, key: str, value: Any, save: bool = True) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            save: 是否保存到文件
        """
        with self.lock:
            old_config = self.config.copy()
            
            # 支持嵌套键
            keys = key.split('.')
            config = self.config
            
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            config[keys[-1]] = value
            
            # 保存到文件
            if save:
                self._save_config()
            
            # 触发变更事件
            self._notify_listeners(ConfigChangeEvent(
                config_path=str(self.config_path),
                change_type='modified',
                timestamp=time.time(),
                old_config=old_config if old_config != self.config else None,
                new_config=self.config.copy()
            ))
            
            logger.info(f"Config updated: {key} = {value}")
    
    def _save_config(self) -> None:
        """保存配置到文件"""
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存配置
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(self.config, f, default_flow_style=False, indent=2)
                else:
                    json.dump(self.config, f, indent=2)
            
            logger.info(f"Config saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def reload_config(self) -> None:
        """手动重新加载配置"""
        logger.info("Manual config reload triggered")
        self.load_config(force=True)
    
    def cleanup(self) -> None:
        """清理资源"""
        self.stop_watching()
        self.change_listeners.clear()
        logger.info("Hot config manager cleaned up")


class HotConfigPluginManager:
    """支持热配置的插件管理器"""
    
    def __init__(self, config_path: str = "plugins.yaml"):
        """
        初始化支持热配置的插件管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_manager = HotConfigManager(config_path)
        
        # 导入原始插件管理器
        from .plugins import PluginManager
        
        self.plugin_manager = PluginManager()
        self.plugin_manager.config = self.config_manager
        
        # 设置配置变更监听器
        self.config_manager.add_change_listener(self._on_config_changed)
        
        logger.info("Hot config plugin manager initialized")
    
    def _on_config_changed(self, event: ConfigChangeEvent) -> None:
        """
        处理配置变更事件
        
        Args:
            event: 配置变更事件
        """
        try:
            logger.info(f"Config changed: {event.change_type}")
            
            # 重新加载插件配置
            self.plugin_manager.config = self.config_manager
            
            # 检查插件配置变化
            if event.old_config and event.new_config:
                self._handle_plugin_config_changes(event.old_config, event.new_config)
            
        except Exception as e:
            logger.error(f"Error handling config change: {e}")
    
    def _handle_plugin_config_changes(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> None:
        """
        处理插件配置变化
        
        Args:
            old_config: 旧配置
            new_config: 新配置
        """
        # 检查启用的插件变化
        old_enabled = set(old_config.get('enabled_plugins', []))
        new_enabled = set(new_config.get('enabled_plugins', []))
        
        # 新启用的插件
        newly_enabled = new_enabled - old_enabled
        for plugin_name in newly_enabled:
            logger.info(f"Plugin newly enabled: {plugin_name}")
            if plugin_name in self.plugin_manager.plugins:
                self.plugin_manager.enable_plugin(plugin_name)
        
        # 新禁用的插件
        newly_disabled = old_enabled - new_enabled
        for plugin_name in newly_disabled:
            logger.info(f"Plugin newly disabled: {plugin_name}")
            if plugin_name in self.plugin_manager.plugins:
                self.plugin_manager.disable_plugin(plugin_name)
        
        # 检查插件配置变化
        old_plugin_configs = old_config.get('plugin_configs', {})
        new_plugin_configs = new_config.get('plugin_configs', {})
        
        for plugin_name in self.plugin_manager.plugins:
            if plugin_name in old_plugin_configs and plugin_name in new_plugin_configs:
                old_plugin_config = old_plugin_configs[plugin_name]
                new_plugin_config = new_plugin_configs[plugin_name]
                
                if old_plugin_config != new_plugin_config:
                    logger.info(f"Plugin config changed: {plugin_name}")
                    # 更新插件配置
                    plugin = self.plugin_manager.plugins[plugin_name]
                    plugin.config = new_plugin_config
                    
                    # 如果插件已启用，重新初始化
                    if plugin.is_enabled():
                        plugin.disable()
                        plugin.enable()
    
    def start_watching(self) -> bool:
        """开始监听配置变化"""
        return self.config_manager.start_watching()
    
    def stop_watching(self) -> None:
        """停止监听配置变化"""
        self.config_manager.stop_watching()
    
    def cleanup(self) -> None:
        """清理资源"""
        self.config_manager.cleanup()
        self.plugin_manager.cleanup()
    
    # 代理插件管理器的方法
    def __getattr__(self, name):
        return getattr(self.plugin_manager, name)


# 全局热配置管理器实例
_hot_config_manager: Optional[HotConfigManager] = None


def get_hot_config_manager(config_path: str = "plugins.yaml") -> HotConfigManager:
    """获取全局热配置管理器实例"""
    global _hot_config_manager
    if _hot_config_manager is None:
        _hot_config_manager = HotConfigManager(config_path)
    return _hot_config_manager


def cleanup_hot_config_system() -> None:
    """清理热配置系统"""
    global _hot_config_manager
    if _hot_config_manager:
        _hot_config_manager.cleanup()
        _hot_config_manager = None