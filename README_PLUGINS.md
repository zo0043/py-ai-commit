# AI Commit - 增强的插件化架构

## 概述

AI Commit 是一个基于Python的AI驱动Git提交消息生成工具，现在具有完整的插件化架构。该工具分析Git差异并使用OpenAI API生成符合传统提交格式的提交消息。

## 🚀 核心特性

### 插件化架构
- **动态插件加载**: 支持运行时插件发现和加载
- **多种插件类型**: 钩子、处理器、集成、UI、缓存、验证器
- **插件生命周期管理**: 完整的初始化、启用、禁用、清理流程
- **依赖关系解析**: 自动解析和管理插件间依赖关系

### 增强的配置管理
- **多源配置支持**: 默认配置、配置文件、环境变量、运行时配置
- **配置验证**: 类型安全的配置验证和模式注册
- **热重载**: 运行时配置重载和合并
- **配置导出**: 支持YAML和JSON格式导出

### 企业级错误处理
- **错误分类系统**: 验证、配置、依赖、执行等错误类别
- **错误上下文跟踪**: 详细的错误上下文和堆栈跟踪
- **自动恢复策略**: 针对不同错误类型的自动恢复机制
- **错误统计分析**: 全面的错误统计和趋势分析

### 性能监控
- **插件性能跟踪**: 加载时间、执行时间、成功率监控
- **系统资源监控**: 内存使用、错误率跟踪
- **性能报告**: 详细的性能摘要和分析报告
- **性能优化**: 基于监控数据的优化建议

## 📦 安装

### 从源码安装
```bash
# 克隆仓库
git clone <repository-url>
cd py-ai-commit

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 开发模式安装
pip install -e .
```

### 配置设置
```bash
# 复制配置模板
cp .aicommit_template .aicommit

# 编辑配置文件
nano .aicommit
```

## 🔧 插件开发

### 插件类型

#### 1. 钩子插件 (HookPlugin)
```python
from ai_commit.plugins import HookPlugin, PluginMetadata, PluginType

class MyHookPlugin(HookPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="my_hook",
            version="1.0.0",
            description="我的钩子插件",
            author="Your Name",
            plugin_type=PluginType.HOOK
        )
    
    def initialize(self):
        # 初始化逻辑
        return True
    
    def cleanup(self):
        # 清理逻辑
        pass
    
    def execute_hook(self, context):
        # 钩子执行逻辑
        result = context.copy()
        result['processed_by'] = 'my_hook'
        return result
```

#### 2. 处理器插件 (ProcessorPlugin)
```python
from ai_commit.plugins import ProcessorPlugin, PluginMetadata, PluginType

class MyProcessorPlugin(ProcessorPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="my_processor",
            version="1.0.0",
            description="我的处理器插件",
            author="Your Name",
            plugin_type=PluginType.PROCESSOR
        )
    
    def initialize(self):
        return True
    
    def cleanup(self):
        pass
    
    def process(self, data):
        # 数据处理逻辑
        return f"Processed: {data}"
```

### 插件配置

#### 配置文件 (plugins.yaml)
```yaml
plugin_directories:
  - plugins
  - custom_plugins

enabled_plugins:
  - commit_message_enhancer
  - pre_commit_hook

disabled_plugins: []

plugin_configs:
  commit_message_enhancer:
    max_length: 100
    include_scope: true
    
  pre_commit_hook:
    skip_tests: false
    max_file_size: 1024

auto_load: true
strict_validation: true
log_level: INFO
```

#### 环境变量
```bash
export AI_COMMIT_PLUGIN_DIRS="plugins,custom_plugins"
export AI_COMMIT_ENABLED_PLUGINS="commit_message_enhancer,pre_commit_hook"
export AI_COMMIT_LOG_LEVEL="DEBUG"
export AI_COMMIT_PLUGIN_TIMEOUT=30
```

## 🎯 内置插件

### 1. 提交消息增强器 (commit_message_enhancer)
- **功能**: 增强AI生成的提交消息
- **特性**: 
  - 添加上下文信息
  - 格式化消息结构
  - 验证消息规范

### 2. 预提交钩子 (pre_commit_hook)
- **功能**: 提交前代码质量检查
- **特性**:
  - 代码语法验证
  - 文件大小检查
  - 测试状态验证
  - 提交消息格式验证

## 📊 监控和调试

### 性能监控
```python
from ai_commit.plugins import get_plugin_manager

# 获取插件管理器
manager = get_plugin_manager()

# 获取系统健康状态
health = manager.get_system_health()
print(f"总插件数: {health['total_plugins']}")
print(f"启用插件数: {health['enabled_plugins']}")
print(f"依赖冲突: {len(health['dependency_conflicts'])}")

# 获取插件性能摘要
for plugin_name in manager.plugins.keys():
    summary = manager.performance_monitor.get_plugin_performance_summary(plugin_name)
    print(f"{plugin_name}: 加载时间 {summary['load_time']:.2f}s")
```

### 错误处理
```python
# 获取错误统计
error_stats = manager.error_handler.get_error_stats()
print(f"总错误数: {error_stats['total_errors']}")

# 获取最近错误
recent_errors = manager.error_handler.get_recent_errors(5)
for error in recent_errors:
    print(f"{error['timestamp']}: {error['message']}")
```

## 🛠️ 开发命令

### 测试
```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_enhanced_plugins.py

# 运行测试并显示覆盖率
python -m pytest tests/ --cov=ai_commit
```

### 调试
```bash
# 启用详细日志
export AI_COMMIT_LOG_LEVEL=DEBUG

# 运行工具
ai-commit -v

# 检查插件状态
ai-commit --plugin-status
```

## 🔍 插件系统架构

### 核心组件

#### 1. PluginManager
- 插件发现和加载
- 生命周期管理
- 依赖关系解析
- 性能监控集成

#### 2. PluginConfigManager
- 多源配置管理
- 配置验证和类型安全
- 热重载支持
- 配置导出功能

#### 3. PluginErrorHandler
- 错误分类和处理
- 错误上下文跟踪
- 自动恢复策略
- 错误统计分析

#### 4. PluginPerformanceMonitor
- 性能数据收集
- 执行时间监控
- 系统资源跟踪
- 性能报告生成

### 插件接口

#### PluginInterface (基类)
```python
class PluginInterface(ABC):
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        pass
    
    def enable(self) -> bool:
        pass
    
    def disable(self) -> None:
        pass
```

## 📝 最佳实践

### 1. 插件开发
- **单一职责**: 每个插件只负责一个特定功能
- **错误处理**: 实现适当的错误处理和日志记录
- **配置验证**: 验证插件配置的完整性和有效性
- **性能考虑**: 避免阻塞操作，使用异步处理

### 2. 配置管理
- **环境变量**: 使用环境变量配置部署相关设置
- **配置文件**: 使用配置文件管理插件特定设置
- **配置验证**: 实现配置验证以确保设置正确
- **默认值**: 提供合理的默认配置值

### 3. 错误处理
- **错误分类**: 使用适当的错误类别
- **上下文信息**: 提供详细的错误上下文
- **恢复策略**: 实现自动恢复机制
- **日志记录**: 记录足够的调试信息

## 🔄 迁移指南

### 从旧版本迁移
1. **备份现有配置**
2. **安装新版本**
3. **更新配置文件格式**
4. **测试插件兼容性**
5. **验证功能完整性**

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🔗 相关链接

- [文档](https://github.com/your-repo/docs)
- [问题跟踪](https://github.com/your-repo/issues)
- [示例插件](https://github.com/your-repo/examples)

---

**注意**: 这是一个活跃开发的项目，API和配置可能会发生变化。请定期检查更新和文档。