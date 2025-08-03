"""
分布式缓存系统演示

演示Redis和内存缓存的使用。
"""

import asyncio
import time
from ai_commit.cache.distributed_cache import (
    DistributedCacheManager, CacheBackend, get_distributed_cache_manager
)

async def demo_memory_cache():
    """演示内存缓存"""
    print("=== 内存缓存演示 ===\n")
    
    # 创建内存缓存管理器
    cache_manager = DistributedCacheManager(CacheBackend.MEMORY, max_size=1000)
    
    # 演示基本操作
    print("1. 基本缓存操作...")
    
    # 设置值
    await cache_manager.set("key1", "value1", ttl=10)
    await cache_manager.set("key2", {"data": "complex"}, ttl=10)
    await cache_manager.set("key3", [1, 2, 3, 4, 5], ttl=10)
    
    print("   ✅ 缓存值已设置")
    
    # 获取值
    value1 = await cache_manager.get("key1")
    value2 = await cache_manager.get("key2")
    value3 = await cache_manager.get("key3")
    
    print(f"   获取的值:")
    print(f"     key1: {value1}")
    print(f"     key2: {value2}")
    print(f"     key3: {value3}")
    
    # 检查存在性
    exists = await cache_manager.exists("key1")
    print(f"   key1 存在: {exists}")
    
    # 删除值
    deleted = await cache_manager.delete("key1")
    print(f"   删除 key1: {deleted}")
    
    # 再次检查存在性
    exists = await cache_manager.exists("key1")
    print(f"   key1 存在: {exists}")
    
    # 获取统计信息
    stats = await cache_manager.get_stats()
    print(f"\n2. 缓存统计:")
    print(f"   后端: {stats['backend']}")
    print(f"   命中率: {stats['manager_stats']['hit_rate']:.2%}")
    print(f"   操作数: {stats['manager_stats']['operations']}")
    print(f"   平均延迟: {stats['manager_stats']['avg_latency_ms']:.3f}ms")
    print(f"   健康检查: {stats['health_check']}")
    
    # 清理
    await cache_manager.cleanup()
    print("\n   ✅ 内存缓存演示完成")


async def demo_redis_cache():
    """演示Redis缓存"""
    print("\n=== Redis缓存演示 ===\n")
    
    try:
        # 创建Redis缓存管理器
        cache_manager = DistributedCacheManager(
            CacheBackend.REDIS,
            host='localhost',
            port=6379,
            db=0
        )
        
        # 健康检查
        healthy = await cache_manager.health_check()
        print(f"1. Redis健康检查: {'✅ 健康' if healthy else '❌ 不健康'}")
        
        if not healthy:
            print("   ⚠️  Redis服务不可用，跳过Redis演示")
            await cache_manager.cleanup()
            return
        
        # 演示基本操作
        print("\n2. 基本缓存操作...")
        
        # 设置不同类型的值
        await cache_manager.set("string_key", "Hello Redis!", ttl=60)
        await cache_manager.set("dict_key", {"name": "AI Commit", "version": "1.0.0"}, ttl=60)
        await cache_manager.set("list_key", [1, 2, 3, 4, 5], ttl=60)
        await cache_manager.set("complex_key", {
            "users": ["alice", "bob", "charlie"],
            "settings": {"theme": "dark", "language": "en"}
        }, ttl=60)
        
        print("   ✅ 各种类型的值已设置")
        
        # 获取值
        string_val = await cache_manager.get("string_key")
        dict_val = await cache_manager.get("dict_key")
        list_val = await cache_manager.get("list_key")
        complex_val = await cache_manager.get("complex_key")
        
        print(f"   获取的值:")
        print(f"     string_key: {string_val}")
        print(f"     dict_key: {dict_val}")
        print(f"     list_key: {list_val}")
        print(f"     complex_key: {complex_val}")
        
        # 演示TTL
        print("\n3. TTL演示...")
        await cache_manager.set("ttl_key", "This will expire", ttl=2)
        print("   设置2秒TTL的键")
        
        # 立即获取
        exists_before = await cache_manager.exists("ttl_key")
        print(f"   立即检查存在性: {exists_before}")
        
        # 等待3秒
        print("   等待3秒...")
        await asyncio.sleep(3)
        
        # 再次检查
        exists_after = await cache_manager.exists("ttl_key")
        value_after = await cache_manager.get("ttl_key")
        print(f"   3秒后存在性: {exists_after}")
        print(f"   3秒后值: {value_after}")
        
        # 性能测试
        print("\n4. 性能测试...")
        
        # 批量操作
        start_time = time.time()
        
        for i in range(100):
            await cache_manager.set(f"perf_key_{i}", f"value_{i}", ttl=60)
        
        set_time = time.time() - start_time
        
        start_time = time.time()
        
        for i in range(100):
            await cache_manager.get(f"perf_key_{i}")
        
        get_time = time.time() - start_time
        
        print(f"   批量设置100个键: {set_time:.3f}s")
        print(f"   批量获取100个键: {get_time:.3f}s")
        print(f"   平均设置时间: {set_time/100*1000:.3f}ms")
        print(f"   平均获取时间: {get_time/100*1000:.3f}ms")
        
        # 获取统计信息
        stats = await cache_manager.get_stats()
        print(f"\n5. Redis缓存统计:")
        print(f"   后端: {stats['backend']}")
        print(f"   命中率: {stats['manager_stats']['hit_rate']:.2%}")
        print(f"   操作数: {stats['manager_stats']['operations']}")
        print(f"   平均延迟: {stats['manager_stats']['avg_latency_ms']:.3f}ms")
        print(f"   健康检查: {stats['health_check']}")
        
        # 清理
        print("\n6. 清理...")
        await cache_manager.clear()
        print("   ✅ Redis缓存已清空")
        
        await cache_manager.cleanup()
        print("   ✅ Redis缓存演示完成")
        
    except Exception as e:
        print(f"   ❌ Redis演示出错: {e}")
        print("   ⚠️  请确保Redis服务正在运行")


async def demo_cache_comparison():
    """演示缓存性能对比"""
    print("\n=== 缓存性能对比演示 ===\n")
    
    # 创建不同后端的缓存管理器
    memory_cache = DistributedCacheManager(CacheBackend.MEMORY, max_size=1000)
    
    try:
        redis_cache = DistributedCacheManager(
            CacheBackend.REDIS,
            host='localhost',
            port=6379,
            db=0
        )
        
        redis_available = await redis_cache.health_check()
    except Exception:
        redis_cache = None
        redis_available = False
    
    # 测试数据
    test_data = {
        "user_id": 12345,
        "username": "test_user",
        "email": "test@example.com",
        "preferences": {
            "theme": "dark",
            "language": "en",
            "notifications": True
        },
        "metadata": {
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
    }
    
    # 测试次数
    test_iterations = 1000
    
    print(f"1. 性能对比测试 ({test_iterations} 次操作)...")
    
    # 测试内存缓存
    print("\n   测试内存缓存...")
    start_time = time.time()
    
    for i in range(test_iterations):
        key = f"memory_test_{i % 100}"  # 使用100个不同的键
        await memory_cache.set(key, test_data, ttl=60)
        await memory_cache.get(key)
    
    memory_time = time.time() - start_time
    memory_stats = await memory_cache.get_stats()
    
    print(f"   内存缓存总时间: {memory_time:.3f}s")
    print(f"   内存缓存平均延迟: {memory_time/test_iterations*1000:.3f}ms")
    print(f"   内存缓存命中率: {memory_stats['manager_stats']['hit_rate']:.2%}")
    
    # 测试Redis缓存
    if redis_available and redis_cache:
        print("\n   测试Redis缓存...")
        start_time = time.time()
        
        for i in range(test_iterations):
            key = f"redis_test_{i % 100}"  # 使用100个不同的键
            await redis_cache.set(key, test_data, ttl=60)
            await redis_cache.get(key)
        
        redis_time = time.time() - start_time
        redis_stats = await redis_cache.get_stats()
        
        print(f"   Redis缓存总时间: {redis_time:.3f}s")
        print(f"   Redis缓存平均延迟: {redis_time/test_iterations*1000:.3f}ms")
        print(f"   Redis缓存命中率: {redis_stats['manager_stats']['hit_rate']:.2%}")
        
        # 性能对比
        print(f"\n   性能对比:")
        if redis_time > 0:
            speed_ratio = memory_time / redis_time
            print(f"   内存缓存 vs Redis: {speed_ratio:.2f}x {'更快' if speed_ratio > 1 else '更慢'}")
        
    else:
        print("\n   ⚠️  Redis不可用，跳过Redis测试")
    
    # 清理
    await memory_cache.cleanup()
    if redis_cache:
        await redis_cache.cleanup()
    
    print("\n   ✅ 缓存性能对比演示完成")


async def demo_cache_features():
    """演示缓存高级特性"""
    print("\n=== 缓存高级特性演示 ===\n")
    
    # 创建缓存管理器
    cache_manager = DistributedCacheManager(CacheBackend.MEMORY, max_size=500)
    
    print("1. 缓存淘汰策略演示...")
    
    # 设置大量数据触发淘汰
    print("   设置600个数据点（缓存大小限制为500）...")
    for i in range(600):
        await cache_manager.set(f"eviction_test_{i}", f"value_{i}", ttl=60)
    
    # 检查一些键是否还存在
    exists_early = await cache_manager.exists("eviction_test_10")
    exists_late = await cache_manager.exists("eviction_test_590")
    
    print(f"   早期键存在: {exists_early}")
    print(f"   晚期键存在: {exists_late}")
    
    # 获取统计
    stats = await cache_manager.get_stats()
    print(f"   淘汰次数: {stats['cache_stats']['evictions']}")
    
    print("\n2. 缓存键生成策略演示...")
    
    # 演示不同的键生成策略
    import hashlib
    
    # 简单键
    simple_key = "user:12345:profile"
    await cache_manager.set(simple_key, {"name": "Alice"}, ttl=60)
    
    # 哈希键
    complex_data = {"large": "data" * 100}
    hash_key = hashlib.md5(str(complex_data).encode()).hexdigest()[:16]
    await cache_manager.set(hash_key, complex_data, ttl=60)
    
    # 组合键
    combo_key = f"session:{hashlib.md5('user123'.encode()).hexdigest()[:8]}:data"
    await cache_manager.set(combo_key, {"session_id": "abc123"}, ttl=60)
    
    print(f"   简单键: {simple_key}")
    print(f"   哈希键: {hash_key}")
    print(f"   组合键: {combo_key}")
    
    # 验证键都可以获取
    simple_val = await cache_manager.get(simple_key)
    hash_val = await cache_manager.get(hash_key)
    combo_val = await cache_manager.get(combo_key)
    
    print(f"   简单键值: {simple_val is not None}")
    print(f"   哈希键值: {hash_val is not None}")
    print(f"   组合键值: {combo_val is not None}")
    
    print("\n3. 缓存健康检查演示...")
    
    # 健康检查
    healthy = await cache_manager.health_check()
    print(f"   健康状态: {'✅ 健康' if healthy else '❌ 不健康'}")
    
    # 获取详细统计
    stats = await cache_manager.get_stats()
    print(f"   详细统计:")
    for key, value in stats['manager_stats'].items():
        if isinstance(value, float):
            print(f"     {key}: {value:.3f}")
        else:
            print(f"     {key}: {value}")
    
    # 清理
    await cache_manager.cleanup()
    print("\n   ✅ 缓存高级特性演示完成")


async def main():
    """主演示函数"""
    print("AI Commit 分布式缓存系统演示")
    print("=" * 50)
    
    # 内存缓存演示
    await demo_memory_cache()
    
    # Redis缓存演示
    await demo_redis_cache()
    
    # 性能对比演示
    await demo_cache_comparison()
    
    # 高级特性演示
    await demo_cache_features()
    
    print("\n🎉 分布式缓存系统演示完成!")


if __name__ == "__main__":
    asyncio.run(main())