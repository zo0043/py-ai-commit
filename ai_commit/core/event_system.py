"""
事件驱动架构核心组件

实现基于事件总线的松耦合架构，支持异步处理和扩展。
"""

import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    GIT_OPERATION = "git_operation"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CONFIG_CHANGE = "config_change"
    ERROR_OCCURRED = "error_occurred"
    PERFORMANCE_METRIC = "performance_metric"
    USER_ACTION = "user_action"


@dataclass
class Event:
    """事件数据结构"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    source: str
    priority: int = 1  # 1-5, 5为最高优先级
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now()


class EventSubscriber:
    """事件订阅者"""
    
    def __init__(self, callback: Callable[[Event], None], 
                 event_types: List[EventType] = None,
                 filter_func: Callable[[Event], bool] = None):
        """
        初始化事件订阅者
        
        Args:
            callback: 事件处理回调函数
            event_types: 订阅的事件类型列表
            filter_func: 事件过滤函数
        """
        self.callback = callback
        self.event_types = set(event_types) if event_types else set()
        self.filter_func = filter_func
        self.subscriber_id = str(uuid.uuid4())
        self.call_count = 0
        self.last_called = None
    
    def can_handle(self, event: Event) -> bool:
        """检查是否可以处理该事件"""
        # 检查事件类型
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        # 检查过滤函数
        if self.filter_func and not self.filter_func(event):
            return False
        
        return True
    
    def handle(self, event: Event) -> None:
        """处理事件"""
        try:
            self.callback(event)
            self.call_count += 1
            self.last_called = datetime.now()
        except Exception as e:
            logger.error(f"Event handler failed for subscriber {self.subscriber_id}: {e}")


class EventBus:
    """事件总线系统"""
    
    def __init__(self, max_queue_size: int = 10000):
        """
        初始化事件总线
        
        Args:
            max_queue_size: 事件队列最大大小
        """
        self.subscribers: Dict[str, EventSubscriber] = {}
        self.event_queue = asyncio.Queue(maxsize=max_queue_size)
        self.is_running = False
        self.processing_task = None
        self.event_stats = {
            'published': 0,
            'processed': 0,
            'failed': 0,
            'queue_size': 0
        }
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def start(self) -> None:
        """启动事件总线"""
        if self.is_running:
            return
        
        self.is_running = True
        self.processing_task = asyncio.create_task(self._process_events())
        logger.info("Event bus started")
    
    async def stop(self) -> None:
        """停止事件总线"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        self.executor.shutdown(wait=True)
        logger.info("Event bus stopped")
    
    def subscribe(self, subscriber: EventSubscriber) -> str:
        """
        订阅事件
        
        Args:
            subscriber: 事件订阅者
            
        Returns:
            订阅者ID
        """
        self.subscribers[subscriber.subscriber_id] = subscriber
        logger.debug(f"Subscribed {subscriber.subscriber_id} to event bus")
        return subscriber.subscriber_id
    
    def unsubscribe(self, subscriber_id: str) -> bool:
        """
        取消订阅
        
        Args:
            subscriber_id: 订阅者ID
            
        Returns:
            是否成功取消订阅
        """
        if subscriber_id in self.subscribers:
            del self.subscribers[subscriber_id]
            logger.debug(f"Unsubscribed {subscriber_id} from event bus")
            return True
        return False
    
    async def publish(self, event: Event) -> None:
        """
        发布事件
        
        Args:
            event: 要发布的事件
        """
        try:
            await self.event_queue.put(event)
            self.event_stats['published'] += 1
            self.event_stats['queue_size'] = self.event_queue.qsize()
            logger.debug(f"Published event {event.event_id} of type {event.event_type}")
        except asyncio.QueueFull:
            logger.error(f"Event queue full, dropping event {event.event_id}")
            self.event_stats['failed'] += 1
    
    async def _process_events(self) -> None:
        """处理事件队列中的事件"""
        while self.is_running:
            try:
                # 等待事件
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # 找到所有可以处理该事件的订阅者
                handlers = []
                for subscriber in self.subscribers.values():
                    if subscriber.can_handle(event):
                        handlers.append(subscriber)
                
                if handlers:
                    # 并行处理事件
                    tasks = []
                    for handler in handlers:
                        task = asyncio.get_event_loop().run_in_executor(
                            self.executor, handler.handle, event
                        )
                        tasks.append(task)
                    
                    # 等待所有处理器完成
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # 统计处理结果
                    success_count = sum(1 for result in results if not isinstance(result, Exception))
                    failed_count = len(results) - success_count
                    
                    self.event_stats['processed'] += success_count
                    self.event_stats['failed'] += failed_count
                    
                    if failed_count > 0:
                        logger.warning(f"Event {event.event_id} failed for {failed_count} handlers")
                
                # 标记事件为已处理
                self.event_queue.task_done()
                
            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                self.event_stats['failed'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取事件总线统计信息"""
        return {
            **self.event_stats,
            'subscribers_count': len(self.subscribers),
            'is_running': self.is_running,
            'queue_size': self.event_queue.qsize()
        }
    
    def get_subscriber_stats(self) -> Dict[str, Any]:
        """获取订阅者统计信息"""
        stats = {}
        for subscriber_id, subscriber in self.subscribers.items():
            stats[subscriber_id] = {
                'call_count': subscriber.call_count,
                'last_called': subscriber.last_called,
                'event_types': [et.value for et in subscriber.event_types],
                'has_filter': subscriber.filter_func is not None
            }
        return stats


class EventManager:
    """事件管理器 - 提供便捷的事件发布接口"""
    
    def __init__(self, event_bus: EventBus):
        """
        初始化事件管理器
        
        Args:
            event_bus: 事件总线实例
        """
        self.event_bus = event_bus
    
    async def publish_git_operation(self, operation: str, 
                                  duration: float, success: bool,
                                  details: Dict[str, Any] = None) -> None:
        """发布Git操作事件"""
        event = Event(
            event_id="",
            event_type=EventType.GIT_OPERATION,
            timestamp=datetime.now(),
            data={
                'operation': operation,
                'duration': duration,
                'success': success,
                'details': details or {}
            },
            source="git_operations",
            priority=2
        )
        await self.event_bus.publish(event)
    
    async def publish_cache_event(self, event_type: EventType, 
                                 cache_key: str, hit: bool,
                                 access_time: float = 0.0) -> None:
        """发布缓存事件"""
        event = Event(
            event_id="",
            event_type=event_type,
            timestamp=datetime.now(),
            data={
                'cache_key': cache_key,
                'hit': hit,
                'access_time': access_time
            },
            source="cache_system",
            priority=1
        )
        await self.event_bus.publish(event)
    
    async def publish_error(self, error_type: str, error_message: str,
                           context: Dict[str, Any] = None) -> None:
        """发布错误事件"""
        event = Event(
            event_id="",
            event_type=EventType.ERROR_OCCURRED,
            timestamp=datetime.now(),
            data={
                'error_type': error_type,
                'error_message': error_message,
                'context': context or {}
            },
            source="error_handler",
            priority=5  # 最高优先级
        )
        await self.event_bus.publish(event)
    
    async def publish_performance_metric(self, metric_name: str, 
                                       value: float, unit: str = "ms") -> None:
        """发布性能指标事件"""
        event = Event(
            event_id="",
            event_type=EventType.PERFORMANCE_METRIC,
            timestamp=datetime.now(),
            data={
                'metric_name': metric_name,
                'value': value,
                'unit': unit
            },
            source="performance_monitor",
            priority=1
        )
        await self.event_bus.publish(event)
    
    async def publish_user_action(self, action: str, 
                                 details: Dict[str, Any] = None) -> None:
        """发布用户操作事件"""
        event = Event(
            event_id="",
            event_type=EventType.USER_ACTION,
            timestamp=datetime.now(),
            data={
                'action': action,
                'details': details or {}
            },
            source="user_interface",
            priority=3
        )
        await self.event_bus.publish(event)


# 全局事件总线实例
_event_bus: Optional[EventBus] = None
_event_manager: Optional[EventManager] = None


async def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
        await _event_bus.start()
    return _event_bus


async def get_event_manager() -> EventManager:
    """获取全局事件管理器实例"""
    global _event_manager
    if _event_manager is None:
        event_bus = await get_event_bus()
        _event_manager = EventManager(event_bus)
    return _event_manager


async def shutdown_event_system() -> None:
    """关闭事件系统"""
    global _event_bus, _event_manager
    if _event_bus:
        await _event_bus.stop()
        _event_bus = None
    _event_manager = None