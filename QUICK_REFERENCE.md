# 知识库同步快速参考

## 最常用命令

```bash
# 完整流程（爬取 + 分类 + 入库 + 同步知识库）
python run_filter.py crawl 30

# 只同步知识库（禁用旧文档 + 提交新案例）
python run_filter.py sync-kb

# 只同步知识库，不禁用旧文档
python run_filter.py sync-kb --no-disable-old
```

## 配置检查

```bash
# 验证配置文件
python scripts/verify_kb_config.py

# 查看待同步数量（不执行）
python run_filter.py sync-kb --dry-run
```

## 关键配置

在 `config/kb_sync.local.json` 中：

```json
{
  "dify": {
    "dataset_id": "28522cdc-67e0-414d-83b1-fada32f48958"
  }
}
```

**重要**：`dataset_id` 必须存在，确保只操作"法律案例知识库"。

## 工作流程

```
1. 爬取法律条文和案例
   ↓
2. Dify 智能分类
   ↓
3. 生成 CSV 文件
   ↓
4. 导入数据库（去重）
   ↓
5. 同步到知识库
   ├─ 禁用旧文档（只针对法律案例知识库）
   └─ 提交新案例
```

## 同步行为

### 默认行为（推荐）

```bash
python run_filter.py sync-kb
```

- ✅ 禁用"法律案例知识库"中的旧文档
- ✅ 提交新案例
- ✅ 更新数据库状态

### 跳过禁用

```bash
python run_filter.py sync-kb --no-disable-old
```

- ❌ 不禁用旧文档
- ✅ 提交新案例
- ✅ 更新数据库状态

## 常见问题

### Q: 为什么需要禁用旧文档？

A: 避免知识库中存在重复或过时的案例。每次同步时，先禁用旧案例，再添加新案例。

### Q: 会影响其他知识库吗？

A: 不会。禁用操作只针对配置中指定的知识库 ID（`28522cdc-67e0-414d-83b1-fada32f48958`），不影响其他知识库。

### Q: 如果禁用失败怎么办？

A: 单个文档禁用失败不会中断流程，会记录警告并继续处理其他文档。新案例仍会正常提交。

### Q: 如何确认同步成功？

A: 查看日志文件 `logs/law-push.log`，成功的案例会标记为"是否同步到知识库=是"。

### Q: 提交失败的案例会怎样？

A: 保持"是否同步到知识库=否"状态，下次运行时会自动重试。

## 故障排查

### 1. 配置错误

```bash
# 运行验证脚本
python scripts/verify_kb_config.py

# 检查输出，确保：
# - 配置文件存在
# - dataset_id 正确
# - API key 有效
```

### 2. 权限问题

确保 API key 有以下权限：
- 读取文档列表
- 禁用文档
- 创建新文档

### 3. 网络问题

检查 Dify 服务器连接：
```bash
curl http://ciduai.daneng.cc/v1/datasets/{dataset_id}/documents?limit=1
```

### 4. 数据库问题

确保数据库连接正常：
```bash
python run_filter.py check-config
```

## 性能提示

### 小批量测试

首次使用建议小批量测试：

```bash
# 限制同步 10 个案例
python run_filter.py sync-kb --limit 10
```

### 查看待同步数量

运行前查看有多少案例待同步：

```bash
python run_filter.py sync-kb --dry-run
```

### 大量文档

如果知识库有大量文档（> 1000 个），禁用过程可能需要几分钟。请耐心等待，不要中断进程。

## 日志查看

```bash
# Windows
type logs\law-push.log | findstr "disable"

# Linux/Mac
tail -f logs/law-push.log | grep disable
```

关键日志消息：
- `已禁用 N 个旧文档` - 禁用完成
- `禁用文档 {doc_id} 失败` - 某个文档禁用失败
- `成功将 N 个案例同步到知识库` - 同步完成

## 测试命令

```bash
# 运行单元测试
python -m pytest tests/test_kb_sync.py -v

# 验证配置
python scripts/verify_kb_config.py

# 模拟测试禁用功能
python scripts/test_disable_function.py
```

## 相关文档

- [完整变更说明](CHANGES.md)
- [功能详细说明](docs/kb_sync_improvements.md)
- [验证清单](VERIFICATION_CHECKLIST.md)
- [主 README](README.md)

## 紧急回退

如果需要禁用这个功能，使用 `--no-disable-old`：

```bash
python run_filter.py sync-kb --no-disable-old
```

这将恢复到之前的行为：只提交新案例，不禁用旧文档。
