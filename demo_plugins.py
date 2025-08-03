"""
插件系统使用示例

演示如何使用AI Commit的插件系统。
"""

import asyncio
import logging
from ai_commit.plugins import PluginManager, get_plugin_manager
from ai_commit.core.event_system import get_event_manager, EventType

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """插件系统使用示例"""
    
    # 获取插件管理器
    plugin_manager = PluginManager("demo_plugins_config.yaml")
    
    # 设置事件管理器
    event_manager = await get_event_manager()
    plugin_manager.set_event_manager(event_manager)
    
    print("=== AI Commit 插件系统演示 ===\n")
    
    # 1. 发现插件
    print("1. 发现插件...")
    discovered_plugins = plugin_manager.discover_plugins()
    print(f"   发现的插件: {discovered_plugins}")
    
    # 2. 加载插件
    print("\n2. 加载插件...")
    loaded_plugins = []
    for plugin_name in discovered_plugins:
        success = plugin_manager.load_plugin(plugin_name)
        if success:
            loaded_plugins.append(plugin_name)
        print(f"   {plugin_name}: {'✅ 成功' if success else '❌ 失败'}")
    
    # 3. 启用插件
    print("\n3. 启用插件...")
    enabled_plugins = []
    for plugin_name in loaded_plugins:
        if plugin_manager.get_plugin(plugin_name):
            success = plugin_manager.enable_plugin(plugin_name)
            if success:
                enabled_plugins.append(plugin_name)
            print(f"   {plugin_name}: {'✅ 已启用' if success else '❌ 启用失败'}")
    
    # 4. 显示插件状态
    print("\n4. 插件状态:")
    status = plugin_manager.get_plugin_status()
    for plugin_name, info in status.items():
        status_icon = "✅" if info['enabled'] else "❌"
        print(f"   {status_icon} {plugin_name} ({info['metadata']['type']})")
        print(f"      版本: {info['metadata']['version']}")
        print(f"      描述: {info['metadata']['description']}")
    
    # 5. 演示钩子执行
    if 'pre_commit_hook_standalone' in enabled_plugins:
        print("\n5. 演示钩子执行...")
        context = {
            'staged_files': ['example.py', 'utils/helper.py'],
            'commit_message': 'feat: add new feature',
            'branch': 'feature/new-feature',
            'author': 'Developer'
        }
        
        print("   执行提交前钩子...")
        hook_result = plugin_manager.execute_hook('pre_commit', context)
        
        if 'pre_commit_results' in hook_result:
            results = hook_result['pre_commit_results']
            if results['passed']:
                print("   ✅ 钩子执行通过")
            else:
                print("   ❌ 钩子执行失败")
                print(f"      错误: {results['errors']}")
            
            if results['warnings']:
                print(f"      警告: {results['warnings']}")
    
    # 6. 演示数据处理
    if 'commit_message_enhancer_standalone' in enabled_plugins:
        print("\n6. 演示数据处理...")
        test_message = "feat: add authentication system"
        print(f"   原始消息: {test_message}")
        
        enhanced_message = plugin_manager.process_data(test_message)
        print(f"   增强后消息: {enhanced_message}")
    
    # 7. 演示插件配置
    print("\n7. 演示插件配置...")
    for plugin_name in enabled_plugins:
        plugin = plugin_manager.get_plugin(plugin_name)
        if plugin:
            print(f"   {plugin_name} 配置:")
            print(f"      检查代码质量: {plugin.get_config('check_code_quality', True)}")
            print(f"      最大文件大小: {plugin.get_config('max_file_size', 1024*1024)}")
    
    # 8. 显示统计信息
    print("\n8. 插件统计:")
    enabled_count = len(plugin_manager.get_enabled_plugins())
    total_count = len(plugin_manager.plugins)
    print(f"   总插件数: {total_count}")
    print(f"   已启用: {enabled_count}")
    print(f"   已禁用: {total_count - enabled_count}")
    
    # 9. 清理
    print("\n9. 清理插件系统...")
    plugin_manager.cleanup()
    await shutdown_event_system()
    print("   ✅ 清理完成")


async def shutdown_event_system():
    """关闭事件系统"""
    from ai_commit.core.event_system import shutdown_event_system
    await shutdown_event_system()


def demo_plugin_types():
    """演示不同类型的插件"""
    print("\n=== 插件类型演示 ===")
    
    from ai_commit.plugins import PluginType
    
    plugin_types = {
        PluginType.HOOK: "钩子插件 - 在特定事件点执行",
        PluginType.PROCESSOR: "处理器插件 - 处理和转换数据",
        PluginType.INTEGRATION: "集成插件 - 与外部系统集成",
        PluginType.UI: "UI插件 - 增强用户界面",
        PluginType.CACHE: "缓存插件 - 提供缓存功能",
        PluginType.VALIDATOR: "验证器插件 - 验证数据"
    }
    
    for plugin_type, description in plugin_types.items():
        print(f"• {plugin_type.value}: {description}")


def demo_plugin_config():
    """演示插件配置"""
    print("\n=== 插件配置演示 ===")
    
    from ai_commit.plugins import PluginConfig
    
    # 创建配置
    config = PluginConfig("demo_plugins.yaml")
    
    # 显示默认配置
    print("默认配置:")
    for key, value in config.config.items():
        print(f"  {key}: {value}")
    
    # 设置插件配置
    print("\n设置插件配置...")
    config.set_plugin_config('pre_commit_hook', {
        'check_code_quality': True,
        'max_file_size': 1024 * 1024,
        'forbidden_patterns': ['TODO', 'FIXME']
    })
    
    # 获取插件配置
    plugin_config = config.get_plugin_config('pre_commit_hook')
    print(f"插件配置: {plugin_config}")
    
    # 启用/禁用插件
    print("\n管理插件状态...")
    config.enable_plugin('pre_commit_hook')
    print(f"pre_commit_hook 启用状态: {config.is_plugin_enabled('pre_commit_hook')}")
    
    config.disable_plugin('pre_commit_hook')
    print(f"pre_commit_hook 启用状态: {config.is_plugin_enabled('pre_commit_hook')}")


if __name__ == "__main__":
    print("AI Commit 插件系统演示")
    print("=" * 50)
    
    # 运行插件类型演示
    demo_plugin_types()
    
    # 运行插件配置演示
    demo_plugin_config()
    
    # 运行主要演示
    print("\n开始主要演示...")
    asyncio.run(main())