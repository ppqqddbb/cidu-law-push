# 知识库同步功能修改总结

## 问题描述

之前的实现在同步知识库时会关闭所有知识库的文档，这是不正确的。应该只关闭"法律案例知识库"（ID: `28522cdc-67e0-414d-83b1-fada32f48958`）中的文档。

## 解决方案

### 1. 配置文件修改

在 `config/kb_sync.local.json` 和 `config/kb_sync.example.json` 中添加了 `dataset_id` 字段：

```json
{
  "dify": {
    "base_url": "http://ciduai.daneng.cc/v1",
    "api_key": "dataset-SCSruW9H3bsFMvFxBk1n4eUz",
    "dataset_name": "法律案例知识库",
    "dataset_id": "28522cdc-67e0-414d-83b1-fada32f48958"
  }
}
```

### 2. 代码功能增强

#### 新增函数：`disable_old_documents()`

位置：`src/law_push/knowledge_base.py`

功能：
- 禁用指定知识库中的所有旧文档
- 支持分页处理大量文档
- 只禁用当前启用的文档（`enabled=True`）
- 跳过已经禁用的文档
- 单个文档禁用失败不影响其他文档

```python
def disable_old_documents(session: requests.Session, dify: dict[str, Any], dataset_id: str) -> int:
    """Disable all documents in the specified dataset before syncing new ones."""
```

#### 修改函数：`synchronize()`

新增参数：
- `disable_old: bool = True` - 是否在同步前禁用旧文档

行为：
- 默认情况下，在同步新文档前先禁用指定知识库的旧文档
- 可以通过设置 `disable_old=False` 跳过此步骤

#### 修改函数：`main()`

新增命令行参数：
- `--no-disable-old` - 同步前不禁用知识库中的旧文档

### 3. 测试更新

更新了 `tests/test_kb_sync.py`，新增测试用例：
- `test_disable_old_documents_is_called_by_default()` - 验证默认会禁用旧文档
- `test_disable_old_can_be_skipped()` - 验证可以跳过禁用步骤

所有测试通过：10 个测试用例全部成功。

### 4. 辅助脚本

创建了两个验证脚本：

#### `scripts/verify_kb_config.py`
验证配置文件是否正确，包括：
- 配置文件是否存在
- 必需字段是否完整
- 知识库 ID 是否正确

#### `scripts/test_disable_function.py`
模拟测试禁用功能，验证：
- 只禁用指定知识库的文档
- 只禁用启用状态的文档
- 正确跳过已禁用的文档

## 使用方法

### 方式 1：默认行为（推荐）

```bash
python run_filter.py sync-kb
```

这将自动禁用"法律案例知识库"中的旧文档，然后同步新文档。

### 方式 2：跳过禁用旧文档

```bash
python run_filter.py sync-kb --no-disable-old
```

这将只同步新文档，不禁用旧文档。

### 方式 3：完整流程

```bash
python run_filter.py crawl 30
```

这将执行完整的流程，包括爬取、分类、生成文件、导入数据库和同步知识库。

## 技术细节

### API 调用流程

1. **获取文档列表**
   ```
   GET /datasets/{dataset_id}/documents?page=1&limit=100
   ```

2. **禁用单个文档**
   ```
   POST /datasets/{dataset_id}/documents/{doc_id}/status
   Body: {"enabled": false}
   ```

3. **创建新文档**
   ```
   POST /datasets/{dataset_id}/document/create-by-text
   Body: {
     "name": "case-{fid}",
     "text": "...",
     "indexing_technique": "high_quality",
     "process_rule": {"mode": "automatic"}
   }
   ```

### 关键逻辑

```python
# 1. 解析知识库 ID
dataset = resolve_dataset(session, dify)

# 2. 禁用旧文档（如果启用）
if disable_old:
    disabled = disable_old_documents(session, dify, dataset)
    logger.info("已禁用 %d 个旧文档（知识库 ID: %s）", disabled, dataset)

# 3. 同步新文档
for candidate in rows:
    # 提交新文档到知识库
    response = session.post(endpoint, json={...})
    # 更新数据库状态
    db.execute("UPDATE ... SET fk_r8p0_sync_kb='否' WHERE fid=%s", (fid,))
```

## 验证清单

- [x] 配置文件包含正确的知识库 ID
- [x] 代码只操作指定的知识库
- [x] 单元测试全部通过
- [x] 配置验证脚本成功
- [x] 功能测试脚本成功
- [x] 文档更新完成

## 影响范围

### 修改的文件
- `config/kb_sync.local.json` - 添加 dataset_id
- `config/kb_sync.example.json` - 添加 dataset_id
- `src/law_push/knowledge_base.py` - 新增禁用功能
- `build/lib/law_push/knowledge_base.py` - 同步更新
- `tests/test_kb_sync.py` - 更新测试用例

### 新增的文件
- `docs/kb_sync_improvements.md` - 功能说明文档
- `scripts/verify_kb_config.py` - 配置验证脚本
- `scripts/test_disable_function.py` - 功能测试脚本
- `CHANGES.md` - 本文档

## 注意事项

1. **数据安全**：首次使用前建议备份知识库数据
2. **权限要求**：确保 API key 有禁用文档的权限
3. **性能考虑**：如果知识库有大量文档，禁用过程可能需要一些时间
4. **错误恢复**：如果禁用失败，可以使用 `--no-disable-old` 跳过此步骤

## 未来改进建议

1. 添加增量同步功能，只禁用需要更新的文档
2. 支持批量禁用 API（如果 Dify 提供）
3. 添加禁用前的确认提示
4. 支持从禁用状态恢复文档

## 测试结果

```
✓ 单元测试: 10/10 通过
✓ 配置验证: 通过
✓ 功能测试: 通过
✓ 语法检查: 通过
```

## 相关链接

- [知识库同步改进说明](docs/kb_sync_improvements.md)
- [配置验证脚本](scripts/verify_kb_config.py)
- [功能测试脚本](scripts/test_disable_function.py)
