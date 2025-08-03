"""
增强的插件错误处理和日志记录模块

提供全面的错误处理、日志记录和调试功能，支持插件系统的稳定性和可维护性。
"""

import logging
import traceback
import sys
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
from pathlib import Path

from ..exceptions import PluginError, ConfigurationError

logger = logging.getLogger(__name__)


class ErrorLevel(Enum):
    """错误级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别枚举"""
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    EXECUTION = "execution"
    INITIALIZATION = "initialization"
    CLEANUP = "cleanup"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """错误上下文信息"""
    plugin_name: str
    operation: str
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginError:
    """插件错误信息"""
    error_id: str
    level: ErrorLevel
    category: ErrorCategory
    message: str
    context: ErrorContext
    stack_trace: Optional[str] = None
    error_data: Dict[str, Any] = field(default_factory=dict)
    recovery_suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class PluginErrorHandler:
    """插件错误处理器"""
    
    def __init__(self, log_dir: str = "logs"):
        """
        初始化错误处理器
        
        Args:
            log_dir: 日志目录
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 错误统计
        self.error_stats = {
            'total_errors': 0,
            'errors_by_level': {},
            'errors_by_category': {},
            'errors_by_plugin': {},
            'recent_errors': []
        }
        
        # 错误处理器注册
        self.error_handlers: Dict[ErrorCategory, List[Callable]] = {}
        
        # 错误恢复策略
        self.recovery_strategies = {
            ErrorCategory.VALIDATION: self._handle_validation_error,
            ErrorCategory.CONFIGURATION: self._handle_configuration_error,
            ErrorCategory.DEPENDENCY: self._handle_dependency_error,
            ErrorCategory.EXECUTION: self._handle_execution_error,
            ErrorCategory.INITIALIZATION: self._handle_initialization_error,
            ErrorCategory.CLEANUP: self._handle_cleanup_error,
            ErrorCategory.TIMEOUT: self._handle_timeout_error,
            ErrorCategory.PERMISSION: self._handle_permission_error,
            ErrorCategory.UNKNOWN: self._handle_unknown_error
        }
        
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """设置日志记录"""
        # 错误日志处理器
        error_handler = logging.FileHandler(
            self.log_dir / "plugin_errors.log",
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        
        # 调试日志处理器
        debug_handler = logging.FileHandler(
            self.log_dir / "plugin_debug.log",
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        
        # 性能日志处理器
        perf_handler = logging.FileHandler(
            self.log_dir / "plugin_performance.log",
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        error_handler.setFormatter(formatter)
        debug_handler.setFormatter(formatter)
        perf_handler.setFormatter(formatter)
        
        # 添加到根日志器
        root_logger = logging.getLogger()
        root_logger.addHandler(error_handler)
        root_logger.addHandler(debug_handler)
        root_logger.addHandler(perf_handler)
    
    def handle_error(self, 
                    exception: Exception,
                    context: ErrorContext,
                    level: ErrorLevel = ErrorLevel.ERROR,
                    category: Optional[ErrorCategory] = None) -> PluginError:
        """
        处理错误
        
        Args:
            exception: 异常对象
            context: 错误上下文
            level: 错误级别
            category: 错误类别
            
        Returns:
            处理后的错误信息
        """
        # 确定错误类别
        if category is None:
            category = self._categorize_error(exception)
        
        # 创建错误对象
        error = PluginError(
            error_id=self._generate_error_id(),
            level=level,
            category=category,
            message=str(exception),
            context=context,
            stack_trace=traceback.format_exc(),
            error_data=self._extract_error_data(exception)
        )
        
        # 添加恢复建议
        error.recovery_suggestions = self._generate_recovery_suggestions(error)
        
        # 记录错误
        self._log_error(error)
        
        # 更新统计
        self._update_error_stats(error)
        
        # 执行错误处理器
        self._execute_error_handlers(error)
        
        # 尝试恢复
        self._attempt_recovery(error)
        
        return error
    
    def _categorize_error(self, exception: Exception) -> ErrorCategory:
        """错误分类"""
        exception_type = type(exception)
        
        if isinstance(exception, ConfigurationError):
            return ErrorCategory.CONFIGURATION
        elif isinstance(exception, PluginError):
            return ErrorCategory.EXECUTION
        elif "validation" in str(exception_type).lower():
            return ErrorCategory.VALIDATION
        elif "dependency" in str(exception).lower():
            return ErrorCategory.DEPENDENCY
        elif "timeout" in str(exception).lower():
            return ErrorCategory.TIMEOUT
        elif "permission" in str(exception).lower():
            return ErrorCategory.PERMISSION
        elif "initialization" in str(exception).lower():
            return ErrorCategory.INITIALIZATION
        elif "cleanup" in str(exception).lower():
            return ErrorCategory.CLEANUP
        else:
            return ErrorCategory.UNKNOWN
    
    def _generate_error_id(self) -> str:
        """生成错误ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"plugin_error_{timestamp}_{id(self) % 10000}"
    
    def _extract_error_data(self, exception: Exception) -> Dict[str, Any]:
        """提取错误数据"""
        return {
            'exception_type': type(exception).__name__,
            'exception_module': type(exception).__module__,
            'exception_args': list(exception.args),
            'exception_repr': repr(exception)
        }
    
    def _generate_recovery_suggestions(self, error: PluginError) -> List[str]:
        """生成恢复建议"""
        suggestions = []
        
        if error.category == ErrorCategory.VALIDATION:
            suggestions.extend([
                "检查插件配置格式是否正确",
                "验证所有必需的配置项",
                "查看插件文档了解配置要求"
            ])
        elif error.category == ErrorCategory.CONFIGURATION:
            suggestions.extend([
                "检查配置文件路径和权限",
                "验证配置文件格式",
                "重置为默认配置"
            ])
        elif error.category == ErrorCategory.DEPENDENCY:
            suggestions.extend([
                "安装缺失的依赖项",
                "检查依赖版本兼容性",
                "更新插件依赖关系"
            ])
        elif error.category == ErrorCategory.EXECUTION:
            suggestions.extend([
                "检查插件代码逻辑",
                "验证输入数据",
                "查看详细日志信息"
            ])
        elif error.category == ErrorCategory.TIMEOUT:
            suggestions.extend([
                "增加超时时间设置",
                "优化插件性能",
                "检查网络连接"
            ])
        elif error.category == ErrorCategory.PERMISSION:
            suggestions.extend([
                "检查文件系统权限",
                "验证用户权限设置",
                "运行权限检查命令"
            ])
        
        return suggestions
    
    def _log_error(self, error: PluginError) -> None:
        """记录错误"""
        # 选择适当的日志级别
        log_level = {
            ErrorLevel.DEBUG: logging.DEBUG,
            ErrorLevel.INFO: logging.INFO,
            ErrorLevel.WARNING: logging.WARNING,
            ErrorLevel.ERROR: logging.ERROR,
            ErrorLevel.CRITICAL: logging.CRITICAL
        }[error.level]
        
        # 记录错误日志
        logger.log(log_level, f"Plugin Error: {error.message}", extra={
            'error_id': error.error_id,
            'plugin_name': error.context.plugin_name,
            'operation': error.context.operation,
            'category': error.category.value,
            'level': error.level.value
        })
        
        # 记录详细信息到调试日志
        debug_logger = logging.getLogger(f"plugin.{error.context.plugin_name}")
        debug_logger.debug(f"Error details: {json.dumps(error.error_data, indent=2)}")
        
        # 保存错误到文件
        self._save_error_to_file(error)
    
    def _save_error_to_file(self, error: PluginError) -> None:
        """保存错误到文件"""
        error_file = self.log_dir / f"error_{error.error_id}.json"
        
        error_data = {
            'error_id': error.error_id,
            'level': error.level.value,
            'category': error.category.value,
            'message': error.message,
            'context': {
                'plugin_name': error.context.plugin_name,
                'operation': error.context.operation,
                'timestamp': error.context.timestamp.isoformat(),
                'user_id': error.context.user_id,
                'session_id': error.context.session_id,
                'additional_info': error.context.additional_info
            },
            'stack_trace': error.stack_trace,
            'error_data': error.error_data,
            'recovery_suggestions': error.recovery_suggestions,
            'timestamp': error.timestamp.isoformat()
        }
        
        try:
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(error_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save error to file: {e}")
    
    def _update_error_stats(self, error: PluginError) -> None:
        """更新错误统计"""
        self.error_stats['total_errors'] += 1
        
        # 按级别统计
        level_key = error.level.value
        self.error_stats['errors_by_level'][level_key] = (
            self.error_stats['errors_by_level'].get(level_key, 0) + 1
        )
        
        # 按类别统计
        category_key = error.category.value
        self.error_stats['errors_by_category'][category_key] = (
            self.error_stats['errors_by_category'].get(category_key, 0) + 1
        )
        
        # 按插件统计
        plugin_key = error.context.plugin_name
        self.error_stats['errors_by_plugin'][plugin_key] = (
            self.error_stats['errors_by_plugin'].get(plugin_key, 0) + 1
        )
        
        # 保存最近的错误
        self.error_stats['recent_errors'].append({
            'error_id': error.error_id,
            'message': error.message,
            'plugin_name': error.context.plugin_name,
            'timestamp': error.timestamp.isoformat()
        })
        
        # 限制最近错误列表长度
        if len(self.error_stats['recent_errors']) > 100:
            self.error_stats['recent_errors'] = self.error_stats['recent_errors'][-100:]
    
    def _execute_error_handlers(self, error: PluginError) -> None:
        """执行错误处理器"""
        handlers = self.error_handlers.get(error.category, [])
        
        for handler in handlers:
            try:
                handler(error)
            except Exception as e:
                logger.error(f"Error handler failed: {e}")
    
    def _attempt_recovery(self, error: PluginError) -> None:
        """尝试错误恢复"""
        recovery_strategy = self.recovery_strategies.get(error.category)
        if recovery_strategy:
            try:
                recovery_strategy(error)
            except Exception as e:
                logger.error(f"Recovery strategy failed: {e}")
    
    def _handle_validation_error(self, error: PluginError) -> None:
        """处理验证错误"""
        logger.info(f"Attempting to recover from validation error in {error.context.plugin_name}")
        # 可以添加自动验证逻辑
    
    def _handle_configuration_error(self, error: PluginError) -> None:
        """处理配置错误"""
        logger.info(f"Attempting to recover from configuration error in {error.context.plugin_name}")
        # 可以添加配置重置逻辑
    
    def _handle_dependency_error(self, error: PluginError) -> None:
        """处理依赖错误"""
        logger.info(f"Attempting to recover from dependency error in {error.context.plugin_name}")
        # 可以添加依赖检查逻辑
    
    def _handle_execution_error(self, error: PluginError) -> None:
        """处理执行错误"""
        logger.info(f"Attempting to recover from execution error in {error.context.plugin_name}")
        # 可以添加重试逻辑
    
    def _handle_initialization_error(self, error: PluginError) -> None:
        """处理初始化错误"""
        logger.info(f"Attempting to recover from initialization error in {error.context.plugin_name}")
        # 可以添加重新初始化逻辑
    
    def _handle_cleanup_error(self, error: PluginError) -> None:
        """处理清理错误"""
        logger.info(f"Attempting to recover from cleanup error in {error.context.plugin_name}")
        # 可以添加强制清理逻辑
    
    def _handle_timeout_error(self, error: PluginError) -> None:
        """处理超时错误"""
        logger.info(f"Attempting to recover from timeout error in {error.context.plugin_name}")
        # 可以添加超时重试逻辑
    
    def _handle_permission_error(self, error: PluginError) -> None:
        """处理权限错误"""
        logger.info(f"Attempting to recover from permission error in {error.context.plugin_name}")
        # 可以添加权限检查逻辑
    
    def _handle_unknown_error(self, error: PluginError) -> None:
        """处理未知错误"""
        logger.info(f"Attempting to recover from unknown error in {error.context.plugin_name}")
        # 可以添加通用恢复逻辑
    
    def register_error_handler(self, 
                             category: ErrorCategory, 
                             handler: Callable[[PluginError], None]) -> None:
        """
        注册错误处理器
        
        Args:
            category: 错误类别
            handler: 错误处理器
        """
        if category not in self.error_handlers:
            self.error_handlers[category] = []
        
        self.error_handlers[category].append(handler)
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        return self.error_stats.copy()
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的错误
        
        Args:
            limit: 限制数量
            
        Returns:
            最近错误列表
        """
        return self.error_stats['recent_errors'][-limit:]
    
    def clear_error_stats(self) -> None:
        """清除错误统计"""
        self.error_stats = {
            'total_errors': 0,
            'errors_by_level': {},
            'errors_by_category': {},
            'errors_by_plugin': {},
            'recent_errors': []
        }


class PluginPerformanceMonitor:
    """插件性能监控器"""
    
    def __init__(self, log_dir: str = "logs"):
        """
        初始化性能监控器
        
        Args:
            log_dir: 日志目录
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.performance_data = {
            'plugin_load_times': {},
            'plugin_execution_times': {},
            'plugin_memory_usage': {},
            'plugin_error_rates': {},
            'system_resources': []
        }
        
        self.logger = logging.getLogger("plugin_performance")
    
    def start_plugin_load_timer(self, plugin_name: str) -> str:
        """
        开始插件加载计时
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            计时器ID
        """
        timer_id = f"{plugin_name}_{time.time()}"
        
        if plugin_name not in self.performance_data['plugin_load_times']:
            self.performance_data['plugin_load_times'][plugin_name] = []
        
        self.performance_data['plugin_load_times'][plugin_name].append({
            'timer_id': timer_id,
            'start_time': time.time(),
            'end_time': None,
            'duration': None
        })
        
        return timer_id
    
    def end_plugin_load_timer(self, plugin_name: str, timer_id: str) -> None:
        """
        结束插件加载计时
        
        Args:
            plugin_name: 插件名称
            timer_id: 计时器ID
        """
        if plugin_name in self.performance_data['plugin_load_times']:
            for timer_data in self.performance_data['plugin_load_times'][plugin_name]:
                if timer_data['timer_id'] == timer_id:
                    timer_data['end_time'] = time.time()
                    timer_data['duration'] = timer_data['end_time'] - timer_data['start_time']
                    
                    # 记录性能日志
                    self.logger.info(f"Plugin {plugin_name} loaded in {timer_data['duration']:.2f}s")
                    break
    
    def record_plugin_execution(self, 
                               plugin_name: str, 
                               operation: str, 
                               duration: float,
                               success: bool = True) -> None:
        """
        记录插件执行信息
        
        Args:
            plugin_name: 插件名称
            operation: 操作名称
            duration: 执行时间
            success: 是否成功
        """
        if plugin_name not in self.performance_data['plugin_execution_times']:
            self.performance_data['plugin_execution_times'][plugin_name] = []
        
        execution_data = {
            'operation': operation,
            'duration': duration,
            'success': success,
            'timestamp': time.time()
        }
        
        self.performance_data['plugin_execution_times'][plugin_name].append(execution_data)
        
        # 记录性能日志
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"Plugin {plugin_name} {operation} {status} in {duration:.2f}s")
    
    def get_plugin_performance_summary(self, plugin_name: str) -> Dict[str, Any]:
        """
        获取插件性能摘要
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            性能摘要
        """
        summary = {
            'plugin_name': plugin_name,
            'load_time': None,
            'execution_stats': {
                'total_operations': 0,
                'successful_operations': 0,
                'failed_operations': 0,
                'average_duration': 0,
                'total_duration': 0
            }
        }
        
        # 计算加载时间
        if plugin_name in self.performance_data['plugin_load_times']:
            load_times = self.performance_data['plugin_load_times'][plugin_name]
            if load_times and load_times[-1]['duration'] is not None:
                summary['load_time'] = load_times[-1]['duration']
        
        # 计算执行统计
        if plugin_name in self.performance_data['plugin_execution_times']:
            executions = self.performance_data['plugin_execution_times'][plugin_name]
            
            if executions:
                successful = sum(1 for e in executions if e['success'])
                total_duration = sum(e['duration'] for e in executions)
                
                summary['execution_stats'] = {
                    'total_operations': len(executions),
                    'successful_operations': successful,
                    'failed_operations': len(executions) - successful,
                    'average_duration': total_duration / len(executions),
                    'total_duration': total_duration
                }
        
        return summary
    
    def get_system_performance_summary(self) -> Dict[str, Any]:
        """
        获取系统性能摘要
        
        Returns:
            系统性能摘要
        """
        total_plugins = len(self.performance_data['plugin_load_times'])
        total_operations = sum(
            len(executions) 
            for executions in self.performance_data['plugin_execution_times'].values()
        )
        
        total_load_time = sum(
            data['duration'] 
            for plugin_data in self.performance_data['plugin_load_times'].values()
            for data in plugin_data
            if data['duration'] is not None
        )
        
        total_execution_time = sum(
            data['duration']
            for plugin_data in self.performance_data['plugin_execution_times'].values()
            for data in plugin_data
        )
        
        return {
            'total_plugins': total_plugins,
            'total_operations': total_operations,
            'average_load_time': total_load_time / total_plugins if total_plugins > 0 else 0,
            'total_load_time': total_load_time,
            'average_execution_time': total_execution_time / total_operations if total_operations > 0 else 0,
            'total_execution_time': total_execution_time
        }