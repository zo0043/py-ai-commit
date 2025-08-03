"""
分布式缓存支持

实现Redis和其他分布式缓存系统的支持，提供高性能的分布式缓存解决方案。
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import hashlib
import pickle
from enum import Enum

logger = logging.getLogger(__name__)


class CacheBackend(Enum):
    """缓存后端类型"""
    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"
    DYNAMODB = "dynamodb"


@dataclass
class CacheStats:
    """缓存统计信息"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    errors: int = 0
    total_latency: float = 0.0
    operations: int = 0
    
    @property
    def hit_rate(self) -> float:
        """计算命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def avg_latency(self) -> float:
        """计算平均延迟"""
        return self.total_latency / self.operations if self.operations > 0 else 0.0
    
    def record_hit(self, latency: float = 0.0) -> None:
        """记录缓存命中"""
        self.hits += 1
        self.operations += 1
        self.total_latency += latency
    
    def record_miss(self, latency: float = 0.0) -> None:
        """记录缓存未命中"""
        self.misses += 1
        self.operations += 1
        self.total_latency += latency
    
    def record_eviction(self) -> None:
        """记录缓存淘汰"""
        self.evictions += 1
    
    def record_error(self) -> None:
        """记录错误"""
        self.errors += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hit_rate,
            'evictions': self.evictions,
            'errors': self.errors,
            'avg_latency_ms': self.avg_latency * 1000,
            'operations': self.operations
        }


class DistributedCacheInterface(ABC):
    """分布式缓存接口"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存值"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """清空缓存"""
        pass
    
    @abstractmethod
    async def get_stats(self) -> CacheStats:
        """获取缓存统计"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass


class MemoryCache(DistributedCacheInterface):
    """内存缓存实现（用于测试和开发）"""
    
    def __init__(self, max_size: int = 10000):
        self.cache: Dict[str, Any] = {}
        self.timestamps: Dict[str, float] = {}
        self.ttls: Dict[str, int] = {}
        self.max_size = max_size
        self.stats = CacheStats()
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        start_time = time.time()
        
        async with self.lock:
            # 检查键是否存在
            if key not in self.cache:
                self.stats.record_miss(time.time() - start_time)
                return None
            
            # 检查是否过期
            if self._is_expired(key):
                del self.cache[key]
                del self.timestamps[key]
                del self.ttls[key]
                self.stats.record_miss(time.time() - start_time)
                self.stats.record_eviction()
                return None
            
            # 更新访问时间
            self.timestamps[key] = time.time()
            value = self.cache[key]
            self.stats.record_hit(time.time() - start_time)
            return value
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存值"""
        start_time = time.time()
        
        async with self.lock:
            # 检查是否需要淘汰
            if len(self.cache) >= self.max_size and key not in self.cache:
                self._evict_lru()
            
            # 设置值
            self.cache[key] = value
            self.timestamps[key] = time.time()
            self.ttls[key] = ttl
            
            logger.debug(f"Cache set: {key}")
            return True
    
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        async with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
                del self.ttls[key]
                logger.debug(f"Cache delete: {key}")
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        async with self.lock:
            if key not in self.cache:
                return False
            return not self._is_expired(key)
    
    async def clear(self) -> bool:
        """清空缓存"""
        async with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            self.ttls.clear()
            logger.info("Cache cleared")
            return True
    
    async def get_stats(self) -> CacheStats:
        """获取缓存统计"""
        return self.stats
    
    async def health_check(self) -> bool:
        """健康检查"""
        return True
    
    def _is_expired(self, key: str) -> bool:
        """检查是否过期"""
        if key not in self.ttls:
            return False
        
        return time.time() - self.timestamps[key] > self.ttls[key]
    
    def _evict_lru(self) -> None:
        """淘汰最近最少使用的键"""
        if not self.timestamps:
            return
        
        # 找到最久未使用的键
        lru_key = min(self.timestamps.keys(), key=lambda k: self.timestamps[k])
        
        # 删除该键
        del self.cache[lru_key]
        del self.timestamps[lru_key]
        del self.ttls[lru_key]
        
        self.stats.record_eviction()
        logger.debug(f"Cache eviction: {lru_key}")


class RedisCache(DistributedCacheInterface):
    """Redis缓存实现"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, 
                 db: int = 0, password: str = None):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.redis = None
        self.stats = CacheStats()
        self.connected = False
    
    async def _connect(self) -> bool:
        """连接到Redis"""
        if self.connected and self.redis:
            return True
        
        try:
            import redis.asyncio as redis
            
            # 创建Redis连接
            self.redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # 测试连接
            await self.redis.ping()
            self.connected = True
            logger.info(f"Connected to Redis: {self.host}:{self.port}")
            return True
            
        except ImportError:
            logger.error("redis package not installed. Install with: pip install redis")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        start_time = time.time()
        
        if not await self._connect():
            self.stats.record_error()
            return None
        
        try:
            # 获取值
            value = await self.redis.get(key)
            
            if value is None:
                self.stats.record_miss(time.time() - start_time)
                return None
            
            # 反序列化
            try:
                deserialized = pickle.loads(value.encode('latin-1'))
                self.stats.record_hit(time.time() - start_time)
                return deserialized
            except Exception as e:
                logger.error(f"Failed to deserialize cache value: {e}")
                self.stats.record_error()
                return None
                
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self.stats.record_error()
            self.connected = False
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存值"""
        start_time = time.time()
        
        if not await self._connect():
            self.stats.record_error()
            return False
        
        try:
            # 序列化值
            serialized = pickle.dumps(value)
            
            # 设置值
            result = await self.redis.setex(key, ttl, serialized.decode('latin-1'))
            
            if result:
                logger.debug(f"Redis set: {key}")
                return True
            else:
                self.stats.record_error()
                return False
                
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            self.stats.record_error()
            self.connected = False
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        if not await self._connect():
            self.stats.record_error()
            return False
        
        try:
            result = await self.redis.delete(key)
            if result > 0:
                logger.debug(f"Redis delete: {key}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            self.stats.record_error()
            self.connected = False
            return False
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not await self._connect():
            self.stats.record_error()
            return False
        
        try:
            result = await self.redis.exists(key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            self.stats.record_error()
            self.connected = False
            return False
    
    async def clear(self) -> bool:
        """清空缓存"""
        if not await self._connect():
            self.stats.record_error()
            return False
        
        try:
            await self.redis.flushdb()
            logger.info("Redis cache cleared")
            return True
            
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            self.stats.record_error()
            self.connected = False
            return False
    
    async def get_stats(self) -> CacheStats:
        """获取缓存统计"""
        if not await self._connect():
            return self.stats
        
        try:
            # 获取Redis信息
            info = await self.redis.info('memory')
            used_memory = int(info.get('used_memory', 0))
            max_memory = int(info.get('maxmemory', 0))
            
            # 获取键空间统计
            keyspace = await self.redis.info('keyspace')
            total_keys = sum(int(db_info.get('keys', 0)) for db_info in keyspace.values())
            
            logger.debug(f"Redis stats: {total_keys} keys, {used_memory} bytes used")
            return self.stats
            
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            self.stats.record_error()
            return self.stats
    
    async def health_check(self) -> bool:
        """健康检查"""
        if not await self._connect():
            return False
        
        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self.connected = False
            return False


class DistributedCacheManager:
    """分布式缓存管理器"""
    
    def __init__(self, backend: Union[CacheBackend, str] = CacheBackend.MEMORY, **kwargs):
        """
        初始化分布式缓存管理器
        
        Args:
            backend: 缓存后端类型
            **kwargs: 后端特定参数
        """
        if isinstance(backend, str):
            backend = CacheBackend(backend)
        
        self.backend = backend
        self.cache: Optional[DistributedCacheInterface] = None
        self.kwargs = kwargs
        self.stats = CacheStats()
        self._initialize_cache()
    
    def _initialize_cache(self) -> None:
        """初始化缓存后端"""
        try:
            if self.backend == CacheBackend.MEMORY:
                self.cache = MemoryCache(**self.kwargs)
            elif self.backend == CacheBackend.REDIS:
                self.cache = RedisCache(**self.kwargs)
            else:
                logger.warning(f"Unsupported cache backend: {self.backend}")
                self.cache = MemoryCache(**self.kwargs)
            
            logger.info(f"Initialized {self.backend.value} cache backend")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache backend: {e}")
            self.cache = MemoryCache(**self.kwargs)
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        start_time = time.time()
        
        try:
            value = await self.cache.get(key)
            latency = time.time() - start_time
            
            if value is not None:
                self.stats.record_hit(latency)
            else:
                self.stats.record_miss(latency)
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.stats.record_error()
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存值"""
        start_time = time.time()
        
        try:
            result = await self.cache.set(key, value, ttl)
            latency = time.time() - start_time
            
            if result:
                self.stats.record_hit(latency)
            else:
                self.stats.record_miss(latency)
            
            return result
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.stats.record_error()
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        try:
            return await self.cache.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            self.stats.record_error()
            return False
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            return await self.cache.exists(key)
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            self.stats.record_error()
            return False
    
    async def clear(self) -> bool:
        """清空缓存"""
        try:
            return await self.cache.clear()
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            self.stats.record_error()
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        cache_stats = await self.cache.get_stats()
        
        return {
            'backend': self.backend.value,
            'manager_stats': self.stats.get_stats(),
            'cache_stats': cache_stats.get_stats(),
            'health_check': await self.health_check()
        }
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            return await self.cache.health_check()
        except Exception as e:
            logger.error(f"Cache health check error: {e}")
            return False
    
    def switch_backend(self, backend: Union[CacheBackend, str], **kwargs) -> None:
        """切换缓存后端"""
        if isinstance(backend, str):
            backend = CacheBackend(backend)
        
        logger.info(f"Switching cache backend from {self.backend.value} to {backend.value}")
        self.backend = backend
        self.kwargs = kwargs
        self._initialize_cache()
    
    async def cleanup(self) -> None:
        """清理资源"""
        if hasattr(self.cache, 'cleanup'):
            await self.cache.cleanup()
        logger.info("Distributed cache manager cleaned up")


# 全局缓存管理器实例
_cache_manager: Optional[DistributedCacheManager] = None


def get_distributed_cache_manager(backend: Union[CacheBackend, str] = CacheBackend.MEMORY, 
                                **kwargs) -> DistributedCacheManager:
    """获取全局分布式缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = DistributedCacheManager(backend, **kwargs)
    return _cache_manager


async def cleanup_distributed_cache() -> None:
    """清理分布式缓存系统"""
    global _cache_manager
    if _cache_manager:
        await _cache_manager.cleanup()
        _cache_manager = None