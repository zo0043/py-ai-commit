"""
测试插件化架构

验证插件系统的功能和集成。
"""

import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

from ai_commit.plugins import (
    PluginManager, PluginConfig, PluginInterface, PluginMetadata,
    PluginType, PluginStatus, HookPlugin, ProcessorPlugin
)
from ai_commit.plugins.pre_commit_hook import PreCommitHook
from ai_commit.plugins.commit_message_enhancer import CommitMessageEnhancer
from ai_commit.plugins.slack_integration import SlackIntegration
from ai_commit.exceptions import PluginError


class TestPluginSystem(unittest.TestCase):
    """测试插件系统"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_plugins.yaml")
        self.plugin_manager = PluginManager(self.config_path)
    
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        # 清理临时目录中的所有文件
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_plugin_config(self):
        """测试插件配置"""
        config = PluginConfig(self.config_path)
        
        # 测试默认配置
        self.assertIn('plugin_directories', config.config)
        self.assertIn('enabled_plugins', config.config)
        self.assertIn('disabled_plugins', config.config)
        
        # 测试插件配置操作
        config.set_plugin_config('test_plugin', {'key': 'value'})
        self.assertEqual(config.get_plugin_config('test_plugin')['key'], 'value')
        
        # 测试启用/禁用插件
        config.enable_plugin('test_plugin')
        self.assertTrue(config.is_plugin_enabled('test_plugin'))
        
        config.disable_plugin('test_plugin')
        self.assertFalse(config.is_plugin_enabled('test_plugin'))
    
    def test_plugin_metadata(self):
        """测试插件元数据"""
        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type=PluginType.HOOK
        )
        
        self.assertEqual(metadata.name, "test_plugin")
        self.assertEqual(metadata.version, "1.0.0")
        self.assertEqual(metadata.plugin_type, PluginType.HOOK)
    
    def test_pre_commit_hook_plugin(self):
        """测试提交前钩子插件"""
        plugin = PreCommitHook()
        
        # 测试元数据
        metadata = plugin.metadata
        self.assertEqual(metadata.name, "pre_commit_hook")
        self.assertEqual(metadata.plugin_type, PluginType.HOOK)
        
        # 测试初始化
        self.assertTrue(plugin.initialize())
        self.assertTrue(plugin.is_initialized())
        
        # 测试钩子执行
        context = {
            'staged_files': ['test.py'],
            'commit_message': 'feat: add test feature'
        }
        
        result = plugin.execute_hook(context)
        self.assertIn('pre_commit_results', result)
        self.assertIn('passed', result['pre_commit_results'])
        
        # 测试清理
        plugin.cleanup()
    
    def test_commit_message_enhancer(self):
        """测试提交信息增强器插件"""
        plugin = CommitMessageEnhancer()
        
        # 测试元数据
        metadata = plugin.metadata
        self.assertEqual(metadata.name, "commit_message_enhancer")
        self.assertEqual(metadata.plugin_type, PluginType.PROCESSOR)
        
        # 测试初始化
        self.assertTrue(plugin.initialize())
        self.assertTrue(plugin.is_initialized())
        
        # 测试消息处理
        test_message = "feat: add new feature"
        context = {
            'staged_files': ['test.py', 'helper.py'],
            'branch': 'feature/new-feature'
        }
        
        # 测试字符串输入
        result = plugin.process(test_message)
        self.assertIsInstance(result, str)
        
        # 测试字典输入
        result = plugin.process({'commit_message': test_message, **context})
        self.assertIsInstance(result, dict)
        self.assertIn('commit_message', result)
        self.assertTrue(result.get('enhanced', False))
        
        # 测试清理
        plugin.cleanup()
    
    def test_slack_integration(self):
        """测试Slack集成插件"""
        plugin = SlackIntegration({
            'webhook_url': 'https://test.url',
            'channel': '#test'
        })
        
        # 测试元数据
        metadata = plugin.metadata
        self.assertEqual(metadata.name, "slack_integration")
        self.assertEqual(metadata.plugin_type, PluginType.INTEGRATION)
        
        # 测试初始化（有webhook URL应该成功）
        self.assertTrue(plugin.initialize())
        
        # 测试清理
        plugin.cleanup()
    
    def test_plugin_manager(self):
        """测试插件管理器"""
        # 测试插件发现
        discovered = self.plugin_manager.discover_plugins()
        self.assertIsInstance(discovered, list)
        
        # 测试插件状态
        status = self.plugin_manager.get_plugin_status()
        self.assertIsInstance(status, dict)
        
        # 测试按类型获取插件
        hook_plugins = self.plugin_manager.get_plugins_by_type(PluginType.HOOK)
        self.assertIsInstance(hook_plugins, list)
        
        # 测试获取已启用插件
        enabled_plugins = self.plugin_manager.get_enabled_plugins()
        self.assertIsInstance(enabled_plugins, list)
    
    def test_plugin_loading_and_management(self):
        """测试插件加载和管理"""
        # 创建测试插件文件
        plugin_file = Path(self.temp_dir) / "test_plugin.py"
        plugin_file.write_text("""
from ai_commit.plugins import HookPlugin, PluginMetadata, PluginType

class TestPlugin(HookPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type=PluginType.HOOK
        )
    
    def initialize(self):
        self._initialized = True
        return True
    
    def cleanup(self):
        pass
    
    def execute_hook(self, context):
        return {'test_result': True}
""")
        
        # 配置插件目录
        self.plugin_manager.config.config['plugin_directories'] = [self.temp_dir]
        self.plugin_manager.config.enable_plugin('test_plugin')
        
        # 测试插件发现
        discovered = self.plugin_manager.discover_plugins()
        self.assertIn('test_plugin', discovered)
        
        # 测试插件加载
        self.assertTrue(self.plugin_manager.load_plugin('test_plugin'))
        
        # 测试插件获取
        plugin = self.plugin_manager.get_plugin('test_plugin')
        self.assertIsNotNone(plugin)
        self.assertIsInstance(plugin, HookPlugin)
        
        # 测试插件启用
        self.assertTrue(self.plugin_manager.enable_plugin('test_plugin'))
        self.assertTrue(plugin.is_enabled())
        
        # 测试插件禁用
        self.assertTrue(self.plugin_manager.disable_plugin('test_plugin'))
        self.assertFalse(plugin.is_enabled())
        
        # 测试插件卸载
        self.assertTrue(self.plugin_manager.unload_plugin('test_plugin'))
        self.assertIsNone(self.plugin_manager.get_plugin('test_plugin'))
    
    def test_hook_execution(self):
        """测试钩子执行"""
        # 创建测试钩子插件
        class TestHook(HookPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test_hook",
                    version="1.0.0",
                    description="Test hook",
                    author="Test Author",
                    plugin_type=PluginType.HOOK
                )
            
            def initialize(self):
                self._initialized = True
                return True
            
            def cleanup(self):
                pass
            
            def execute_hook(self, context):
                return {'hook_executed': True, 'hook_value': 42}
        
        # 手动添加插件
        hook = TestHook()
        self.plugin_manager.plugins['test_hook'] = hook
        self.plugin_manager.plugin_status['test_hook'] = PluginStatus.ENABLED
        self.plugin_manager.plugin_types[PluginType.HOOK].append('test_hook')
        
        # 启用插件
        hook.enable()
        
        # 执行钩子
        result = self.plugin_manager.execute_hook('test_hook', {'test': 'context'})
        
        self.assertTrue(result['hook_executed'])
        self.assertEqual(result['hook_value'], 42)
        self.assertEqual(result['test'], 'context')  # 原始上下文应该保留
    
    def test_data_processing(self):
        """测试数据处理"""
        # 创建测试处理器插件
        class TestProcessor(ProcessorPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test_processor",
                    version="1.0.0",
                    description="Test processor",
                    author="Test Author",
                    plugin_type=PluginType.PROCESSOR
                )
            
            def initialize(self):
                self._initialized = True
                return True
            
            def cleanup(self):
                pass
            
            def process(self, data):
                if isinstance(data, dict):
                    return {**data, 'processed': True, 'value': data.get('value', 0) * 2}
                elif isinstance(data, str):
                    return f"processed: {data}"
                else:
                    return data
        
        # 手动添加插件
        processor = TestProcessor()
        self.plugin_manager.plugins['test_processor'] = processor
        self.plugin_manager.plugin_status['test_processor'] = PluginStatus.ENABLED
        self.plugin_manager.plugin_types[PluginType.PROCESSOR].append('test_processor')
        
        # 启用插件
        processor.enable()
        
        # 测试数据处理
        test_data = {'value': 21, 'original': True}
        result = self.plugin_manager.process_data(test_data)
        
        self.assertTrue(result['processed'])
        self.assertEqual(result['value'], 42)
        self.assertTrue(result['original'])  # 原始数据应该保留
        
        # 测试字符串处理
        string_result = self.plugin_manager.process_data("test")
        self.assertEqual(string_result, "processed: test")
    
    def test_plugin_manager_cleanup(self):
        """测试插件管理器清理"""
        # 创建测试插件
        class TestPlugin(PluginInterface):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="cleanup_test",
                    version="1.0.0",
                    description="Cleanup test plugin",
                    author="Test Author",
                    plugin_type=PluginType.HOOK
                )
            
            def initialize(self):
                self._initialized = True
                return True
            
            def cleanup(self):
                self.cleaned_up = True
                pass
        
        # 添加插件
        plugin = TestPlugin()
        self.plugin_manager.plugins['cleanup_test'] = plugin
        self.plugin_manager.plugin_metadata['cleanup_test'] = plugin.metadata
        self.plugin_manager.plugin_status['cleanup_test'] = PluginStatus.ENABLED
        self.plugin_manager.plugin_types[PluginType.HOOK].append('cleanup_test')
        plugin.enable()
        
        # 验证插件存在
        self.assertIn('cleanup_test', self.plugin_manager.plugins)
        
        # 清理
        self.plugin_manager.cleanup()
        
        # 验证清理
        self.assertTrue(plugin.cleaned_up)
        self.assertNotIn('cleanup_test', self.plugin_manager.plugins)


if __name__ == '__main__':
    unittest.main()