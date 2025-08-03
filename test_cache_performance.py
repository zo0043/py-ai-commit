#!/usr/bin/env python3
"""
缓存性能测试脚本

测试AI Commit项目的缓存系统性能和命中率统计。
"""

import time
import statistics
from unittest.mock import patch, MagicMock
from ai_commit.git import GitOperations
from ai_commit.utils import FileStatusCache


def test_git_cache_performance():
    """测试Git操作缓存性能"""
    print("🧪 测试Git操作缓存性能...")
    
    git_ops = GitOperations()
    
    # 模拟1000次Git分支获取操作
    branch_times = []
    cached_hits = 0
    
    for i in range(1000):
        start_time = time.time()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="main\n", returncode=0)
            branch = git_ops.get_current_branch()
        
        end_time = time.time()
        branch_times.append(end_time - start_time)
    
    # 获取缓存统计
    cache_stats = git_ops.get_cache_stats()
    
    print(f"✅ Git分支获取缓存测试完成:")
    print(f"   - 总请求数: {len(branch_times)}")
    print(f"   - 缓存命中率: {cache_stats['cache_stats']['hit_rate']:.1%}")
    print(f"   - 平均响应时间: {statistics.mean(branch_times)*1000:.3f}ms")
    print(f"   - 最快响应: {min(branch_times)*1000:.3f}ms")
    print(f"   - 最慢响应: {max(branch_times)*1000:.3f}ms")
    
    return cache_stats, branch_times


def test_file_cache_performance():
    """测试文件状态缓存性能"""
    print("\n🧪 测试文件状态缓存性能...")
    
    file_cache = FileStatusCache()
    
    # 模拟1000次文件状态检查操作
    file_times = []
    test_files = [f"test_file_{i}.py" for i in range(100)]
    
    for i in range(1000):
        start_time = time.time()
        
        # 循环使用测试文件以测试缓存效果
        file_path = test_files[i % len(test_files)]
        
        # 模拟文件状态获取
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat:
            mock_stat.return_value = MagicMock(st_size=1024, st_mtime=time.time())
            
            # 第一次访问会触发缓存未命中
            status = file_cache.get_status(file_path)
            if status is None:
                # 模拟获取新状态
                from ai_commit.utils import FileStatus
                new_status = FileStatus(exists=True, size=1024, modified_time=time.time())
                file_cache.set_status(file_path, new_status)
        
        end_time = time.time()
        file_times.append(end_time - start_time)
    
    # 获取缓存统计
    cache_stats = file_cache.get_stats()
    
    print(f"✅ 文件状态缓存测试完成:")
    print(f"   - 总请求数: {len(file_times)}")
    print(f"   - 缓存命中率: {cache_stats['cache_stats']['hit_rate']:.1%}")
    print(f"   - 平均响应时间: {statistics.mean(file_times)*1000:.3f}ms")
    print(f"   - 缓存大小: {cache_stats['cache_size']}")
    
    return cache_stats, file_times


def test_cache_key_generation():
    """测试缓存键生成性能"""
    print("\n🧪 测试缓存键生成性能...")
    
    git_ops = GitOperations()
    
    # 测试不同参数的缓存键生成
    test_cases = [
        ("git status", []),
        ("git diff", ["--cached"]),
        ("git add", ["file1.py", "file2.py"]),
        ("git commit", ["-m", "test message"]),
    ]
    
    key_times = []
    
    for command, args in test_cases:
        for i in range(1000):
            start_time = time.time()
            key = git_ops._get_cache_key(command, args)
            end_time = time.time()
            key_times.append(end_time - start_time)
    
    print(f"✅ 缓存键生成测试完成:")
    print(f"   - 生成次数: {len(key_times)}")
    print(f"   - 平均生成时间: {statistics.mean(key_times)*1000:.6f}ms")
    print(f"   - 最快生成: {min(key_times)*1000:.6f}ms")
    print(f"   - 最慢生成: {max(key_times)*1000:.6f}ms")
    
    return key_times


def test_cache_memory_usage():
    """测试缓存内存使用"""
    print("\n🧪 测试缓存内存使用...")
    
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # 创建大量缓存条目
    git_ops = GitOperations()
    file_cache = FileStatusCache()
    
    for i in range(1000):
        # 填充Git缓存
        cache_key = f"test_key_{i}"
        git_ops._cache_result(cache_key, f"test_data_{i}")
        
        # 填充文件缓存
        from ai_commit.utils import FileStatus
        file_status = FileStatus(exists=True, size=1024, modified_time=time.time())
        file_cache.set_status(f"test_file_{i}.py", file_status)
    
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    print(f"✅ 缓存内存使用测试完成:")
    print(f"   - 初始内存: {initial_memory:.2f}MB")
    print(f"   - 最终内存: {final_memory:.2f}MB")
    print(f"   - 内存增长: {memory_increase:.2f}MB")
    print(f"   - Git缓存大小: {len(git_ops._cache)}")
    print(f"   - 文件缓存大小: {len(file_cache._cache)}")
    
    return memory_increase


def main():
    """运行所有缓存性能测试"""
    print("🚀 开始AI Commit缓存性能测试")
    print("=" * 50)
    
    try:
        # 测试Git操作缓存
        git_stats, git_times = test_git_cache_performance()
        
        # 测试文件状态缓存
        file_stats, file_times = test_file_cache_performance()
        
        # 测试缓存键生成
        key_times = test_cache_key_generation()
        
        # 测试内存使用
        memory_increase = test_cache_memory_usage()
        
        # 总结报告
        print("\n" + "=" * 50)
        print("📊 缓存性能测试总结")
        print("=" * 50)
        
        print(f"🎯 缓存命中率:")
        print(f"   - Git操作: {git_stats['cache_stats']['hit_rate']:.1%}")
        print(f"   - 文件状态: {file_stats['cache_stats']['hit_rate']:.1%}")
        
        print(f"⚡ 响应性能:")
        print(f"   - Git分支获取: {statistics.mean(git_times)*1000:.3f}ms")
        print(f"   - 文件状态检查: {statistics.mean(file_times)*1000:.3f}ms")
        print(f"   - 缓存键生成: {statistics.mean(key_times)*1000:.6f}ms")
        
        print(f"💾 内存效率:")
        print(f"   - 内存增长: {memory_increase:.2f}MB (1000个缓存条目)")
        print(f"   - 平均每条目: {memory_increase/1000*1024:.2f}KB")
        
        # 性能评级
        overall_hit_rate = (git_stats['cache_stats']['hit_rate'] + file_stats['cache_stats']['hit_rate']) / 2
        if overall_hit_rate > 0.95:
            grade = "🏆 优秀"
        elif overall_hit_rate > 0.85:
            grade = "🥈 良好"
        elif overall_hit_rate > 0.70:
            grade = "🥉 一般"
        else:
            grade = "⚠️ 需要优化"
        
        print(f"\n🏅 综合评级: {grade}")
        print(f"   - 平均缓存命中率: {overall_hit_rate:.1%}")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()