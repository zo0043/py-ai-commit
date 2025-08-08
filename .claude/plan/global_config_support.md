# 全局配置支持 - 执行计划

## 任务描述
升级一个新版本0.3，支持输入acc的时候，默认获取全局的配置文件在home目录下的.aicommit中的配置，然后读取当前目录下的.aicommit的配置，最后获取环境变量中的配置。

## 上下文
- 当前版本：0.2.0
- 目标版本：0.3.0
- 配置系统：位于 ai_commit/config/__init__.py
- 配置优先级：全局配置 → 当前目录配置 → 环境变量

## 执行计划

### 步骤1：修改配置加载逻辑
**文件**：`/Users/zero0043/0043/github/py-ai-commit/ai_commit/config/__init__.py`
**函数**：`ConfigurationLoader._find_config_files`
**逻辑概要**：
- 优先检查`~/.aicommit`全局配置文件
- 然后检查当前目录及上级目录的`.aicommit`文件
- 最后检查环境变量
**预期结果**：实现全局配置优先级系统

### 步骤2：更新版本号
**文件**：`/Users/zero0043/0043/github/py-ai-commit/pyproject.toml`
**修改**：将版本从`0.2.0`更新为`0.3.0`
**预期结果**：版本号正确更新

### 步骤3：更新__init__.py中的版本
**文件**：`/Users/zero0043/0043/github/py-ai-commit/ai_commit/__init__.py`
**修改**：同步更新版本号
**预期结果**：保持版本一致性

### 步骤4：测试配置系统
**测试方法**：
- 创建全局配置文件`~/.aicommit`
- 创建本地配置文件`.aicommit`
- 验证配置优先级
**预期结果**：配置系统正常工作

### 步骤5：验证功能
**测试命令**：
```bash
# 测试基本功能
acc --dry-run

# 测试配置加载
acc config show
```
**预期结果**：所有功能正常

## 时间戳
2025-08-08