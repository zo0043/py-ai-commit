"""
热配置系统演示

演示配置热更新功能。
"""

import asyncio
import time
import yaml
from pathlib import Path
from ai_commit.config.hot_config import HotConfigManager, get_hot_config_manager

# 模拟插件配置
def create_demo_config():
    """创建演示配置"""
    config = {
        'plugin_directories': ['plugins'],
        'enabled_plugins': ['pre_commit_hook_standalone'],
        'disabled_plugins': [],
        'plugin_configs': {
            'pre_commit_hook_standalone': {
                'check_code_quality': True,
                'max_file_size': 1048576,
                'forbidden_patterns': ['TODO', 'FIXME']
            }
        },
        'auto_load': True,
        'strict_validation': False
    }
    return config

def config_change_listener(event):
    """配置变更监听器"""
    print(f"\n🔄 配置变更事件:")
    print(f"   类型: {event.change_type}")
    print(f"   时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))}")
    print(f"   文件: {event.config_path}")
    
    if event.old_config != event.new_config:
        print(f"   配置内容已变更")
        
        # 显示具体变更
        if event.old_config and event.new_config:
            old_enabled = set(event.old_config.get('enabled_plugins', []))
            new_enabled = set(event.new_config.get('enabled_plugins', []))
            
            if old_enabled != new_enabled:
                print(f"   启用的插件变更:")
                if newly_enabled := new_enabled - old_enabled:
                    print(f"     + 新启用: {list(newly_enabled)}")
                if newly_disabled := old_enabled - new_enabled:
                    print(f"     - 新禁用: {list(newly_disabled)}")

async def demo_hot_config():
    """演示热配置功能"""
    print("=== AI Commit 热配置系统演示 ===\n")
    
    # 配置文件路径
    config_path = "demo_hot_config.yaml"
    
    # 创建配置管理器
    config_manager = get_hot_config_manager(config_path)
    
    # 添加变更监听器
    config_manager.add_change_listener(config_change_listener)
    
    # 创建初始配置
    initial_config = create_demo_config()
    
    # 保存初始配置
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(initial_config, f, default_flow_style=False, indent=2)
    
    print(f"1. 创建初始配置文件: {config_path}")
    print(f"   初始配置: {initial_config}")
    
    # 重新加载配置以确保文件被正确读取
    config_manager.load_config(force=True)
    
    # 开始监听
    print("\n2. 开始监听配置文件变化...")
    if config_manager.start_watching():
        print("   ✅ 监听启动成功")
    else:
        print("   ❌ 监听启动失败")
        return
    
    # 等待一下让监听器稳定
    await asyncio.sleep(1)
    
    # 演示1: 修改配置
    print("\n3. 演示配置修改...")
    print("   修改插件配置...")
    
    # 读取当前配置
    current_config = config_manager.get_config()
    
    # 确保plugin_configs存在
    if 'plugin_configs' not in current_config:
        current_config['plugin_configs'] = {}
    
    if 'pre_commit_hook_standalone' not in current_config['plugin_configs']:
        current_config['plugin_configs']['pre_commit_hook_standalone'] = {}
    
    # 修改配置
    current_config['plugin_configs']['pre_commit_hook_standalone']['check_code_quality'] = False
    current_config['plugin_configs']['pre_commit_hook_standalone']['max_file_size'] = 2048576
    
    # 保存修改
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(current_config, f, default_flow_style=False, indent=2)
    
    print("   配置已保存，等待热更新...")
    
    # 等待热更新
    await asyncio.sleep(2)
    
    # 验证配置是否更新
    updated_config = config_manager.get_config()
    check_quality = updated_config.get('plugin_configs', {}).get('pre_commit_hook_standalone', {}).get('check_code_quality')
    max_size = updated_config.get('plugin_configs', {}).get('pre_commit_hook_standalone', {}).get('max_file_size')
    
    print(f"   ✅ 配置已热更新:")
    print(f"      check_code_quality: {check_quality}")
    print(f"      max_file_size: {max_size}")
    
    # 演示2: 启用新插件
    print("\n4. 演示启用新插件...")
    
    # 修改配置启用新插件
    current_config = config_manager.get_config()
    current_config['enabled_plugins'].append('commit_message_enhancer_standalone')
    
    # 保存修改
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(current_config, f, default_flow_style=False, indent=2)
    
    print("   添加新插件到启用列表...")
    
    # 等待热更新
    await asyncio.sleep(2)
    
    # 验证配置
    updated_config = config_manager.get_config()
    enabled_plugins = updated_config.get('enabled_plugins', [])
    
    print(f"   ✅ 插件列表已更新:")
    print(f"      启用的插件: {enabled_plugins}")
    
    # 演示3: 通过API修改配置
    print("\n5. 演示通过API修改配置...")
    
    # 使用API修改配置
    config_manager.set_config('plugin_configs.pre_commit_hook_standalone.forbidden_patterns', ['TODO', 'FIXME', 'HACK'])
    
    print("   通过API修改配置...")
    
    # 等待热更新
    await asyncio.sleep(1)
    
    # 验证配置
    updated_config = config_manager.get_config()
    patterns = updated_config.get('plugin_configs', {}).get('pre_commit_hook_standalone', {}).get('forbidden_patterns', [])
    
    print(f"   ✅ 配置已通过API更新:")
    print(f"      forbidden_patterns: {patterns}")
    
    # 演示4: 手动重新加载
    print("\n6. 演示手动重新加载...")
    
    # 修改配置文件
    current_config = config_manager.get_config()
    current_config['strict_validation'] = True
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(current_config, f, default_flow_style=False, indent=2)
    
    print("   修改配置文件...")
    
    # 手动重新加载
    config_manager.reload_config()
    
    # 验证配置
    updated_config = config_manager.get_config()
    strict_validation = updated_config.get('strict_validation')
    
    print(f"   ✅ 手动重新加载成功:")
    print(f"      strict_validation: {strict_validation}")
    
    # 清理
    print("\n7. 清理...")
    config_manager.cleanup()
    
    # 删除演示文件
    if Path(config_path).exists():
        Path(config_path).unlink()
        print(f"   删除演示配置文件: {config_path}")
    
    print("\n🎉 热配置系统演示完成!")

if __name__ == "__main__":
    asyncio.run(demo_hot_config())