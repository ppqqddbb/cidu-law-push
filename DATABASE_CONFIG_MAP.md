# 数据库配置文件位置图示

## 项目结构（关注数据库配置）

```
Law-Push/
│
├── config/                              ← 配置目录
│   ├── kb_sync.local.json              ← 【主配置文件】数据库连接信息在这里！
│   │   └── database {                   
│   │       "host": "127.0.0.1",        ← 数据库 IP
│   │       "port": 5432,               ← 数据库端口
│   │       "database": "dev_local_4_all", ← 数据库名称
│   │       "user": "postgres",         ← 用户名
│   │       "password": "020513wyt",    ← 密码
│   │       "schema": "public",         ← 模式
│   │       "table": "tk_r8p0_case"    ← 表名
│   │   }
│   ├── kb_sync.example.json            ← 配置模板（新部署时参考）
│   ├── app.local.json                  ← Dify 爬取/分类配置
│   └── kingdee.local.json              ← 金蝶推送配置
│
├── src/law_push/
│   ├── database.py                      ← 【数据库模块】
│   │   ├── load_config()               ← 第 67 行：加载配置函数
│   │   │   ├── 读取 kb_sync.local.json
│   │   │   ├── 解析 database 配置节
│   │   │   └── 支持环境变量覆盖
│   │   └── import_csv()                ← 第 90 行：导入 CSV 到数据库
│   │       ├── 调用 load_config()
│   │       └── 使用配置连接数据库
│   │
│   └── knowledge_base.py                ← 【知识库同步模块】
│       ├── load_config()               ← 第 23 行：加载配置
│       │   └── 调用 database.load_config()
│       └── synchronize()               ← 第 128 行：同步到知识库
│           ├── 读取数据库配置
│           ├── 连接数据库
│           ├── 查询待同步案例
│           └── 提交到 Dify 知识库
│
├── scripts/
│   └── verify_kb_config.py             ← 【配置验证脚本】
│       └── 验证数据库配置是否正确
│
└── run_filter.py                        ← 【命令入口】
    ├── crawl 30                        → 完整流程（含数据库操作）
    ├── import-cases                    → 导入 CSV 到数据库
    └── sync-kb                         → 同步数据库到知识库
```

## 数据流向图

```
┌─────────────────────────────────────────────────────────────────┐
│                     数据库配置使用流程                              │
└─────────────────────────────────────────────────────────────────┘

1️⃣ 爬取阶段
   ┌──────────────┐
   │  爬取法律数据  │
   └──────┬───────┘
          ↓
   ┌──────────────┐
   │  Dify 分类   │
   └──────┬───────┘
          ↓
   ┌──────────────┐
   │ 生成 CSV 文件 │
   └──────┬───────┘
          ↓

2️⃣ 数据库导入阶段
   ┌────────────────────────────────────────┐
   │  database.py: import_csv()            │
   │                                        │
   │  ① load_config()                      │
   │     ↓                                  │
   │  ② 读取 config/kb_sync.local.json     │
   │     ↓                                  │
   │  ③ 解析 database 配置                  │
   │     host: "127.0.0.1"                 │
   │     port: 5432                        │
   │     database: "dev_local_4_all"       │
   │     user: "postgres"                  │
   │     password: "020513wyt"             │
   │     ↓                                  │
   │  ④ psycopg.connect(...)               │
   │     ↓                                  │
   │  ⑤ INSERT INTO tk_r8p0_case          │
   │     设置 fk_r8p0_sync_kb = '是'        │
   └────────────────────────────────────────┘
          ↓

3️⃣ 知识库同步阶段
   ┌────────────────────────────────────────┐
   │  knowledge_base.py: synchronize()     │
   │                                        │
   │  ① load_config()                      │
   │     ↓                                  │
   │  ② 读取 config/kb_sync.local.json     │
   │     ↓                                  │
   │  ③ 解析 database 配置                  │
   │     host: "127.0.0.1"                 │
   │     database: "dev_local_4_all"       │
   │     table: "tk_r8p0_case"             │
   │     ↓                                  │
   │  ④ psycopg.connect(...)               │
   │     ↓                                  │
   │  ⑤ SELECT * FROM tk_r8p0_case        │
   │     WHERE fk_r8p0_sync_kb = '是'      │
   │     ↓                                  │
   │  ⑥ 提交到 Dify 知识库                  │
   │     ↓                                  │
   │  ⑦ UPDATE tk_r8p0_case               │
   │     SET fk_r8p0_sync_kb = '否'        │
   └────────────────────────────────────────┘
```

## 配置文件内容结构

```
config/kb_sync.local.json
├── dify {                              ← Dify 知识库配置
│   ├── base_url                        ← API 地址
│   ├── api_key                         ← API 密钥
│   ├── dataset_name                    ← 知识库名称
│   └── dataset_id                      ← 知识库 ID（精确定位）
│
├── database {                          ← 【数据库配置】★★★
│   ├── driver: "postgresql"            ← 数据库类型
│   ├── host: "127.0.0.1"              ← 【IP 地址】
│   ├── port: 5432                     ← 【端口】
│   ├── database: "dev_local_4_all"    ← 【数据库名称】
│   ├── user: "postgres"               ← 【用户名】
│   ├── password: "020513wyt"          ← 【密码】
│   ├── schema: "public"               ← 【模式名】
│   └── table: "tk_r8p0_case"         ← 【表名】
│
└── state_file: "kb_sync_state.sqlite3" ← 同步状态文件
```

## 代码调用关系

```
run_filter.py
├── crawl
│   └── pipeline.py: run_pipeline()
│       └── database.py: import_csv()
│           └── load_config() → kb_sync.local.json
│
├── import-cases
│   └── database.py: import_csv()
│       └── load_config() → kb_sync.local.json
│
└── sync-kb
    └── knowledge_base.py: synchronize()
        └── load_config() → kb_sync.local.json
            └── database.load_config() → 读取 database 配置
```

## 环境变量覆盖机制

```
┌─────────────────────────────────────────────┐
│          配置优先级（从高到低）               │
└─────────────────────────────────────────────┘

1️⃣ 环境变量（最高优先级）
   export CASE_DB_HOST=192.168.1.100
   export CASE_DB_PORT=5432
   export CASE_DB_NAME=my_database
   export CASE_DB_USER=myuser
   export CASE_DB_PASSWORD=mypassword
   export CASE_DB_SCHEMA=public
   export CASE_DB_TABLE=tk_r8p0_case
   ↓ 覆盖 ↓

2️⃣ JSON 配置文件
   config/kb_sync.local.json
   {
     "database": {
       "host": "127.0.0.1",
       "port": 5432,
       ...
     }
   }
   ↓ 如果没有环境变量 ↓

3️⃣ 默认值（如果都没有则报错）
   required = ("host", "port", "database", 
               "user", "schema", "table")
```

## 快速定位表

| 操作 | 文件/位置 |
|------|----------|
| 修改数据库 IP | `config/kb_sync.local.json` → `database.host` |
| 修改数据库端口 | `config/kb_sync.local.json` → `database.port` |
| 修改数据库名称 | `config/kb_sync.local.json` → `database.database` |
| 修改用户名 | `config/kb_sync.local.json` → `database.user` |
| 修改密码 | `config/kb_sync.local.json` → `database.password` |
| 修改模式名 | `config/kb_sync.local.json` → `database.schema` |
| 修改表名 | `config/kb_sync.local.json` → `database.table` |
| 查看配置加载逻辑 | `src/law_push/database.py:67-87` |
| 查看数据库连接 (导入) | `src/law_push/database.py:96-99` |
| 查看数据库连接 (同步) | `src/law_push/knowledge_base.py:133-136` |
| 验证配置 | `python scripts/verify_kb_config.py` |

## 数据库表字段

```sql
-- 案例表结构
CREATE TABLE tk_r8p0_case (
    fid SERIAL PRIMARY KEY,              -- 案例 ID（自增主键）
    fk_r8p0_title TEXT,                  -- 案例标题
    fk_r8p0_src TEXT,                    -- 案例来源
    fk_r8p0_link TEXT,                   -- 案例链接
    fk_r8p0_pub_date TIMESTAMP,          -- 发布日期
    fk_r8p0_file_date TIMESTAMP,         -- 文件生成日期
    fk_r8p0_content TEXT,                -- 案例内容/摘要
    fk_r8p0_sync_kb VARCHAR(10)          -- 是否同步到知识库 ('是'/'否')
);

-- 索引（用于去重）
CREATE UNIQUE INDEX idx_title_link 
ON tk_r8p0_case (fk_r8p0_title, fk_r8p0_link);
```

## 相关命令速查

```bash
# 查看配置
cat config/kb_sync.local.json

# 验证配置
python scripts/verify_kb_config.py

# 测试数据库连接
python run_filter.py sync-kb --dry-run

# 完整流程（含数据库操作）
python run_filter.py crawl 30

# 只导入数据库
python run_filter.py import-cases

# 只同步知识库
python run_filter.py sync-kb
```
