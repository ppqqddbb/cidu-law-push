# 知识库同步改进说明

## 修改内容

### 1. 添加知识库 ID 配置

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

### 2. 新增功能：禁用旧文档

在 `src/law_push/knowledge_base.py` 中新增了 `disable_old_documents()` 函数，用于在同步新文档前禁用指定知识库中的旧文档。

#### 功能特点：

- **精确定位**：只操作配置中指定的 `dataset_id` 对应的知识库
- **批量处理**：分页获取文档列表，逐个禁用
- **错误处理**：单个文档禁用失败不影响其他文档的处理
- **日志记录**：记录每个禁用操作的结果

### 3. 修改同步流程

`synchronize()` 函数新增 `disable_old` 参数（默认为 `True`）：

- 在同步新文档前，先禁用目标知识库中的所有旧文档
- 确保只操作指定的知识库，不影响其他知识库

### 4. 命令行参数

新增 `--no-disable-old` 参数，允许跳过禁用旧文档的步骤：

```bash
# 默认行为：同步前禁用旧文档
python run_filter.py sync-kb

# 跳过禁用旧文档
python run_filter.py sync-kb --no-disable-old
```

## 使用方法

### 正常同步（推荐）

```bash
python run_filter.py sync-kb
```

这将：
1. 禁用"法律案例知识库"（ID: 28522cdc-67e0-414d-83b1-fada32f48958）中的所有旧文档
2. 将数据库中标记为"是否同步到知识库=是"的案例提交到该知识库
3. 更新数据库中的同步状态为"否"

### 仅同步新文档（不禁用旧文档）

```bash
python run_filter.py sync-kb --no-disable-old
```

### 完整流程

```bash
python run_filter.py crawl 30
```

这将执行：
1. 爬取最近 30 天的法律信息
2. 使用 Dify 分类
3. 生成 TXT/CSV 文件
4. 导入 PostgreSQL 数据库
5. **禁用知识库中的旧文档**
6. 同步新案例到 Dify 知识库

## 技术细节

### API 端点

- 获取文档列表：`GET /datasets/{dataset_id}/documents`
- 更新文档状态：`POST /datasets/{dataset_id}/documents/{doc_id}/status`

### 请求格式

```json
{
  "enabled": false
}
```

### 错误处理

- 文档列表获取失败：抛出异常，中断同步
- 单个文档禁用失败：记录警告，继续处理其他文档
- 整个禁用过程失败：记录警告，继续同步新文档

## 注意事项

1. **权限要求**：确保 API key 有禁用文档的权限
2. **性能影响**：如果知识库中有大量文档，禁用过程可能需要较长时间
3. **数据备份**：建议在首次使用前备份知识库数据
4. **配置验证**：确保 `dataset_id` 正确，避免操作错误的知识库

## 故障排除

### 问题：禁用文档失败

**可能原因**：
- API key 权限不足
- 知识库 ID 不正确
- 网络连接问题

**解决方法**：
1. 检查 API key 权限
2. 验证 `dataset_id` 是否正确
3. 使用 `--no-disable-old` 跳过禁用步骤

### 问题：禁用了错误的知识库

**解决方法**：
1. 检查 `config/kb_sync.local.json` 中的 `dataset_id`
2. 确保 ID 为 `28522cdc-67e0-414d-83b1-fada32f48958`（法律案例知识库）
3. 通过 Dify API 手动恢复文档状态

## 更新日志

- **2026-10-15**：新增知识库 ID 配置和旧文档禁用功能
