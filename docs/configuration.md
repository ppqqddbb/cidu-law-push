# 配置说明

使用 `py310` 环境。运行依赖统一维护在根目录 `requirements.txt`，`pyproject.toml` 从该文件读取依赖。

## 配置文件

| 文件 | 作用 |
| --- | --- |
| `config/app.local.json` | 爬取结果分类使用的 Dify 智能体地址和密钥 |
| `config/kb_sync.local.json` | PostgreSQL 和 Dify 知识库配置 |
| `config/kingdee.local.json` | 仅用于旧金蝶 HTTP 推送 |
| `config/wechat_accounts.yaml` | 已有来源配置，保留原文件 |

本机配置不会进入 Git。首次部署按对应的 `*.example.json` 创建 `*.local.json` 并填写值；不要覆盖已有配置。
分类服务 API 密钥与知识库 API 密钥属于不同用途，不能混用。

`kb_sync.local.json` 的 `database` 包含 `host`、`port`、`database`、`user`、`password`、`schema`、`table`。
`dify` 包含 `base_url`、`api_key`、`dataset_id`、`dataset_name`。
未指定 `dataset_id` 时按名称查找唯一知识库。入库和同步使用相同数据库配置，前端后端也应连接此表。

## 路径与优先级

优先级为命令行显式配置路径 > 配置路径环境变量 > `config/` 下默认文件。
数据库和 Dify 字段的环境变量可覆盖文件内容。显式传入的相对文件路径按当前工作目录解析。

源码运行时，默认目录相对于项目根目录，与当前工作目录无关：

| 变量 | 默认值 / 作用 |
| --- | --- |
| `LAW_PUSH_HOME` | 源码项目根目录；wheel 部署时指定运行目录 |
| `LAW_PUSH_CONFIG_DIR` | `config` |
| `LAW_PUSH_OUTPUT_DIR` | `data/output` |
| `LAW_PUSH_LOG_DIR` | `logs` |
| `LAW_PUSH_APP_CONFIG` | 分类服务配置文件路径 |
| `CASE_DB_CONFIG` | 入库与知识库同步共同的 JSON 配置文件路径 |
| `KINGDEE_CONFIG` | 旧金蝶 HTTP 配置文件路径 |

目录环境变量中的相对路径基于 `LAW_PUSH_HOME`。字段覆盖支持：

- 分类：`DIFY_API_URL`、`DIFY_API_KEY`。
- 数据库：`CASE_DB_HOST`、`CASE_DB_PORT`、`CASE_DB_NAME`、`CASE_DB_USER`、`CASE_DB_PASSWORD`、`CASE_DB_SCHEMA`、`CASE_DB_TABLE`。
- 知识库：`DIFY_KB_BASE_URL`、`DIFY_KB_API_KEY`、`DIFY_KB_DATASET_ID`、`DIFY_KB_DATASET_NAME`。
- 旧金蝶：`KINGDEE_CLIENT_ID`、`KINGDEE_CLIENT_SECRET`、`KINGDEE_USERNAME`、`KINGDEE_ACCOUNT_ID`、`KINGDEE_IDENTITY`、`KINGDEE_TOKEN_URL`、`KINGDEE_CASE_URL`、`KINGDEE_SYNC_KB`。

`python run_filter.py check-config` 只做本机配置检查，不显示凭据、不请求远端。
