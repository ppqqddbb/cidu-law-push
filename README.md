# Law-Push

法律信息采集与案例同步工具。完整流程为：

爬取 → Dify 分类 → 生成 TXT/CSV → PostgreSQL 去重入库 → 提交 Dify 知识库。

运行环境使用 Conda `py310`（Python 3.10）。前端仍通过后端 API 查询数据库，无需上传 CSV。

## 快速运行

```powershell
conda activate py310
cd D:\File\VSCodeFile\QDHB\Law-Push
python -m pip install -r requirements.txt

# 离线检查配置与目录，不请求远端
python .\run_filter.py check-config

# 保留原来的命令：最近 30 天，自动入库并同步知识库
python .\run_filter.py 30

# 启动命令
python setup_daily_task.py
python setup_daily_task.py --time xx:xx
```

现有本机配置已迁移到 `config/`，原有输出已迁移到 `data/output/`。
首次部署到其他机器时，按 [配置说明](docs/configuration.md) 填写本机配置。

## 项目结构

```text
Law-Push/
├── run_filter.py              # 唯一源码启动入口，兼容原命令
├── pyproject.toml             # 包元数据、命令入口、测试配置
├── requirements.txt           # 运行依赖的唯一清单
├── src/law_push/
│   ├── cli.py                 # 统一命令分发
│   ├── pipeline.py            # 爬取到知识库的流程编排
│   ├── crawler.py             # 多来源采集与文件导出
│   ├── classifier.py          # Dify 智能体分类
│   ├── database.py            # CSV 校验、事务入库与去重
│   ├── knowledge_base.py      # 待同步案例分批提交与失败重试
│   ├── kingdee.py             # 旧金蝶 HTTP 协议适配
│   ├── case_push.py           # 旧金蝶推送命令
│   ├── settings.py            # 采集配置与分类服务配置
│   ├── paths.py               # 配置、输出、日志路径
│   ├── logging_config.py      # 控制台及轮转日志
│   ├── diagnostics.py         # 离线配置检查
│   └── file_dates.py          # 日期格式处理
├── config/                    # 配置模板与本机私有配置
├── data/output/               # result.txt、law.txt、case.csv
├── logs/                      # 应用日志及定时任务日志
├── scripts/                   # Windows / Linux 定时任务安装脚本
├── tests/                     # 单元测试及命令入口回归测试
├── docs/                      # 配置、运维与迁移说明
└── archive/legacy/            # 旧脚本归档，不作为运行入口
```

## 统一命令

以下命令均在项目根目录、激活 `py310` 后执行。

| 用途 | 命令 |
| --- | --- |
| 完整流程 | `python .\run_filter.py crawl 30` |
| 兼容旧命令 | `python .\run_filter.py 30` |
| 仅入库，暂不提交知识库 | `python .\run_filter.py crawl 30 --no-sync-kb` |
| 仅生成文件 | `python .\run_filter.py crawl 30 --no-push-case` |
| 补导入默认 CSV | `python .\run_filter.py import-cases` |
| 导入指定 CSV | `python .\run_filter.py import-cases .\data\output\case.csv` |
| 补同步知识库（禁用旧文档） | `python .\run_filter.py sync-kb` |
| 补同步知识库（保留旧文档） | `python .\run_filter.py sync-kb --no-disable-old` |
| 查询待同步数量，不写入 | `python .\run_filter.py sync-kb --dry-run` |
| 旧金蝶 HTTP 推送 | `python .\run_filter.py push-kingdee .\data\output\case.csv` |
| 旧金蝶推送并启用企微推送 | `python .\run_filter.py push-kingdee .\data\output\case.csv --wecom-push 是` |
| 配置检查 | `python .\run_filter.py check-config` |
| 验证知识库配置 | `python scripts\verify_kb_config.py` |
| 查看某个命令的参数 | `python .\run_filter.py crawl --help` |

正常使用完整流程即可，无需另外执行入库和同步命令。补导入仅负责入库，之后可以单独执行 `sync-kb`。

## 安装为标准 Python 命令

```powershell
conda activate py310
python -m pip install -e ".[dev]"
law-push crawl 30
law-push sync-kb --dry-run
python -m law_push check-config
```

源码安装可自动找到项目目录；通过 wheel 部署时设置 `LAW_PUSH_HOME` 指向包含
`config/` 的运行目录。源码启动器可以通过绝对路径从其他工作目录运行。

## 输出与日志

- `data/output/result.txt`：分类前的完整采集结果。
- `data/output/law.txt`：法律条文。
- `data/output/case.csv`：法律案例，UTF-8 BOM 编码。
- `logs/law-push.log`：应用日志，单文件 10 MiB，保留 5 个轮转文件。

发布日与文件生成时间分别保留；`--file-date "2026-09-09 17:30:45"` 可指定文件日期。
相同标题和链接的案例重复入库会跳过。知识库提交失败保留待同步状态，命令返回非零退出码。
Dify 接收文档后异步建立索引；提交成功不代表索引已完成。

## 知识库同步

知识库同步功能会将数据库中标记为"是否同步到知识库=否"的案例提交到 Dify 知识库。

### 同步行为

默认情况下，`sync-kb` 命令会：
1. **禁用旧文档**：禁用"法律案例知识库"（ID: `28522cdc-67e0-414d-83b1-fada32f48958`）中的所有旧文档
2. **提交新案例**：将待同步案例提交到知识库
3. **更新状态**：将成功提交的案例标记为"是否同步到知识库=是"

> 从旧版本升级时，旧数据在提交成功后也被写为“否”，重新安装后会再次提交。
> 若需避免重复提交，请先执行 `law-push sync-kb --mark-synced`，把当前全部案例
> 标记为“是”，再开始使用新的同步逻辑。

### 配置要求

在 `config/kb_sync.local.json` 中需要配置：

```json
{
  "dify": {
    "base_url": "http://ciduai.daneng.cc/v1",
    "api_key": "your-api-key",
    "dataset_name": "法律案例知识库",
    "dataset_id": "28522cdc-67e0-414d-83b1-fada32f48958"
  }
}
```

- `dataset_id`：**必需**，确保只操作指定的知识库
- `dataset_name`：知识库名称，当未指定 `dataset_id` 时用于查找

### 高级选项

```powershell
# 跳过禁用旧文档，只提交新案例
python .\run_filter.py sync-kb --no-disable-old

# 限制本次同步的案例数量
python .\run_filter.py sync-kb --limit 100

# 验证配置是否正确
python scripts\verify_kb_config.py
```

### 注意事项

- **精确定位**：禁用操作只影响配置中指定的知识库，不影响其他知识库
- **失败重试**：提交失败的案例保持待同步状态，下次运行时会重试
- **权限要求**：确保 API key 有禁用文档的权限
- **性能影响**：如果知识库有大量文档，禁用过程可能需要一些时间

详细说明请参考：[知识库同步改进说明](docs/kb_sync_improvements.md)、[变更日志](CHANGES.md)

## 验证与运维

```powershell
python -m pytest
.\scripts\install_daily_filter.ps1 -PythonExecutable 'D:\File\Anaconda\envs\py310\python.exe' -DryRun
```

定时任务安装、失败重试及退出码见 [运维说明](docs/operations.md)。
旧文件位置和命令的对应关系见 [迁移说明](docs/migration.md)。
