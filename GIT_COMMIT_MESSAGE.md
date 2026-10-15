# Git 提交信息

## 提交标题

```
feat: 知识库同步时只禁用指定知识库的文档
```

## 提交详情

```
feat: 知识库同步时只禁用指定知识库的文档

## 问题
之前的实现在同步知识库时会关闭所有知识库的文档，导致其他知识库的文档被错误地禁用。

## 解决方案
1. 在配置文件中添加 dataset_id 字段，明确指定要操作的知识库
2. 实现 disable_old_documents() 函数，只禁用指定知识库的旧文档
3. synchronize() 函数新增 disable_old 参数，默认先禁用旧文档再同步新文档
4. 添加 --no-disable-old 命令行参数，允许跳过禁用步骤

## 主要变更
- config/kb_sync.local.json: 添加 dataset_id 配置项
- config/kb_sync.example.json: 更新配置示例
- src/law_push/knowledge_base.py: 实现禁用旧文档功能
- tests/test_kb_sync.py: 新增测试用例
- README.md: 更新文档说明

## 配置要求
在 config/kb_sync.local.json 中添加：
{
  "dify": {
    "dataset_id": "28522cdc-67e0-414d-83b1-fada32f48958"
  }
}

## 测试
- 单元测试: 10/10 通过
- 配置验证: 通过
- 功能测试: 通过

## 文档
- CHANGES.md: 完整变更记录
- docs/kb_sync_improvements.md: 详细功能说明
- QUICK_REFERENCE.md: 快速参考指南
- VERIFICATION_CHECKLIST.md: 验证清单

## 向后兼容
使用 --no-disable-old 可以恢复到之前的行为（只提交不禁用）。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

## 如果需要分多个提交

### 提交 1: 配置文件

```
feat: 添加知识库 ID 配置项

在 kb_sync 配置中添加 dataset_id 字段，用于精确指定要操作的知识库。

- config/kb_sync.local.json: 添加 dataset_id
- config/kb_sync.example.json: 更新示例

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

### 提交 2: 核心功能

```
feat: 实现禁用指定知识库旧文档的功能

添加 disable_old_documents() 函数，只禁用指定知识库的旧文档。
synchronize() 函数新增 disable_old 参数，默认先禁用旧文档。

- src/law_push/knowledge_base.py: 实现禁用功能
- build/lib/law_push/knowledge_base.py: 同步更新

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

### 提交 3: 测试

```
test: 添加禁用旧文档功能的测试

- tests/test_kb_sync.py: 新增测试用例
- scripts/verify_kb_config.py: 配置验证脚本
- scripts/test_disable_function.py: 功能测试脚本

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

### 提交 4: 文档

```
docs: 更新知识库同步相关文档

- README.md: 添加知识库同步章节
- CHANGES.md: 完整变更记录
- docs/kb_sync_improvements.md: 详细功能说明
- QUICK_REFERENCE.md: 快速参考指南
- VERIFICATION_CHECKLIST.md: 验证清单

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

## 建议

推荐使用单个提交，因为这些变更是一个完整的功能。如果需要更细粒度的版本控制，可以分为 4 个提交。
