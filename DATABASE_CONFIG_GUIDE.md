# 数据库配置位置指南

## 配置文件位置

### 主配置文件

**位置**: `config/kb_sync.local.json`

这是**主要的数据库配置文件**，包含数据库连接信息：

```json
{
  "dify": {
    "base_url": "http://ciduai.daneng.cc/v1",
    "api_key": "dataset-SCSruW9H3bsFMvFxBk1n4eUz",
    "dataset_name": "法律案例知识库",
    "dataset_id": "28522cdc-67e0-414d-83b1-fada32f48958"
  },
  "database": {
    "driver": "postgresql",
    "host": "127.0.0.1",           // 数据库 IP 地址
    "port": 5432,                  // 数据库端口
    "database": "dev_local_4_all", // 数据库名称
    "user": "postgres",            // 数据库用户名
    "password": "020513wyt",       // 数据库密码
    "schema": "public",            // 数据库模式（schema）
    "table": "tk_r8p0_case"       // 案例表名
  },
  "state_file": "kb_sync_state.sqlite3"
}
```

### 配置模板文件

**位置**: `config/kb_sync.example.json`

这是配置模板，用于首次部署时参考：

```json
{
  "database": {
    "driver": "postgresql",
    "host": "",                    // 填写数据库 IP
    "port": 5432,                  // 数据库端口
    "database": "",                // 填写数据库名称
    "user": "",                    // 填写用户名
    "password": "",                // 填写密码
    "schema": "public",            // 模式名
    "table": ""                    // 填写表名
  }
}
```

## 代码中读取配置的位置

### 1. 数据库模块

**文件**: `src/law_push/database.py`

**函数**: `load_config()`（第 67-87 行）

```python
def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载数据库配置，支持 JSON 文件和环境变量"""
    config_path = Path(path or os.getenv("CASE_DB_CONFIG", DEFAULT_CONFIG))
    config: dict[str, Any] = {}
    try:
        if config_path.exists() or path is not None or os.getenv("CASE_DB_CONFIG"):
            payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
            config = dict(payload["database"])  # 读取 database 配置节
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"数据库配置无法读取: {config_path}") from exc
    
    # 支持环境变量覆盖
    aliases = {"database": "NAME"}
    for key in ("host", "port", "database", "user", "password", "schema", "table"):
        value = os.getenv(f"CASE_DB_{aliases.get(key, key.upper())}")
        if value is not None:
            config[key] = int(value) if key == "port" else value
    
    return config
```

**使用位置**: `import_csv()` 函数（第 90-100 行）

```python
def import_csv(path: str | Path, config_path: str | Path | None = None) -> dict[str, int]:
    """导入 CSV 到数据库"""
    records = read_cases(path)
    config = load_config(config_path)  # 加载配置
    
    # 建立数据库连接
    connection = psycopg.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["database"],
        user=config["user"],
        password=config.get("password", ""),
        connect_timeout=5,
        row_factory=dict_row,
    )
    # ...
```

### 2. 知识库同步模块

**文件**: `src/law_push/knowledge_base.py`

**导入**: 第 17 行
```python
from .database import load_config as load_database_config
```

**加载配置**: `load_config()` 函数（第 23-29 行）

```python
def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载知识库同步配置（包含数据库和 Dify 配置）"""
    if path is None:
        path = Path(os.getenv("KB_SYNC_CONFIG", DEFAULT_CONFIG))
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    config = dict(payload)
    config["database"] = load_database_config(path)  # 从同一文件读取数据库配置
    return config
```

**使用配置**: `synchronize()` 函数（第 128-135 行）

```python
def synchronize(config_path: str | Path | None = None, dry_run: bool = False,
                limit: int | None = None, disable_old: bool = True) -> int:
    """同步案例到知识库"""
    config = load_config(config_path)
    database, dify = config["database"], config["dify"]
    
    # 构建表名
    table = sql.Identifier(database["schema"], database["table"])
    
    # 连接数据库
    with psycopg.connect(
        host=database["host"],
        port=database["port"],
        dbname=database["database"],
        user=database["user"],
        password=database.get("password", ""),
        connect_timeout=5,
        row_factory=dict_row
    ) as db:
        # ...
```

## 环境变量配置方式

除了 JSON 配置文件，还支持通过环境变量配置数据库连接：

### 配置文件路径

```bash
# 指定配置文件路径（两种方式）
export CASE_DB_CONFIG=/path/to/config.json    # 用于 database.py
export KB_SYNC_CONFIG=/path/to/config.json    # 用于 knowledge_base.py
```

### 数据库连接参数

```bash
# 覆盖配置文件中的数据库参数
export CASE_DB_HOST=192.168.1.100      # 数据库 IP
export CASE_DB_PORT=5432               # 数据库端口
export CASE_DB_NAME=my_database        # 数据库名称（或 CASE_DB_DATABASE）
export CASE_DB_USER=myuser             # 用户名
export CASE_DB_PASSWORD=mypassword     # 密码
export CASE_DB_SCHEMA=public           # 模式名
export CASE_DB_TABLE=my_table          # 表名
```

**优先级**: 环境变量 > JSON 配置文件

## 配置验证

### 方法 1: 检查配置文件

```bash
# 验证配置文件格式和必需字段
python scripts/verify_kb_config.py
```

### 方法 2: 系统诊断

```bash
# 完整的系统配置检查
python run_filter.py check-config
```

### 方法 3: 测试数据库连接

```bash
# 尝试导入 CSV（dry-run 模式）
python run_filter.py import-cases --help
```

## 修改数据库配置的步骤

### 步骤 1: 编辑配置文件

```bash
# Windows
notepad config\kb_sync.local.json

# Linux/Mac
nano config/kb_sync.local.json
```

### 步骤 2: 修改数据库参数

```json
{
  "database": {
    "host": "新的IP地址",
    "port": 新的端口,
    "database": "新的数据库名",
    "user": "新的用户名",
    "password": "新的密码",
    "schema": "新的schema",
    "table": "新的表名"
  }
}
```

### 步骤 3: 验证配置

```bash
python scripts/verify_kb_config.py
```

### 步骤 4: 测试连接

```bash
# 查询待同步数量（不写入数据库）
python run_filter.py sync-kb --dry-run
```

## 常见数据库配置场景

### 场景 1: 本地开发环境

```json
{
  "database": {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "dev_local_4_all",
    "user": "postgres",
    "password": "your_password",
    "schema": "public",
    "table": "tk_r8p0_case"
  }
}
```

### 场景 2: 远程服务器

```json
{
  "database": {
    "host": "192.168.1.100",
    "port": 5432,
    "database": "production_db",
    "user": "app_user",
    "password": "secure_password",
    "schema": "public",
    "table": "tk_r8p0_case"
  }
}
```

### 场景 3: 云数据库（如阿里云 RDS）

```json
{
  "database": {
    "host": "rm-xxxxxx.mysql.rds.aliyuncs.com",
    "port": 5432,
    "database": "law_push_prod",
    "user": "law_push_user",
    "password": "cloud_password",
    "schema": "public",
    "table": "tk_r8p0_case"
  }
}
```

## 数据库表结构

案例表 (`tk_r8p0_case`) 的关键字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `fid` | 主键 | 案例唯一标识 |
| `fk_r8p0_title` | 文本 | 案例标题 |
| `fk_r8p0_src` | 文本 | 案例来源 |
| `fk_r8p0_link` | 文本 | 案例链接 |
| `fk_r8p0_pub_date` | 时间戳 | 发布日期 |
| `fk_r8p0_file_date` | 时间戳 | 文件生成日期 |
| `fk_r8p0_content` | 文本 | 案例内容/摘要 |
| `fk_r8p0_sync_kb` | 文本 | 是否同步到知识库 ("是"/"否") |

## 安全注意事项

### 1. 保护配置文件

```bash
# 确保配置文件不被提交到版本控制
# .gitignore 中已包含：
config/*.local.json
```

### 2. 使用环境变量（生产环境推荐）

```bash
# 不要在代码中硬编码密码
# 使用环境变量或密钥管理服务
export CASE_DB_PASSWORD=$(cat /secure/path/db_password)
```

### 3. 限制数据库用户权限

- 只授予必要的权限（SELECT, INSERT, UPDATE）
- 不要使用 postgres 超级用户
- 为应用创建专用数据库用户

### 4. 使用 SSL 连接（可选）

在 `psycopg.connect()` 中添加：
```python
sslmode='require'
```

## 相关文件快速参考

| 文件 | 说明 |
|------|------|
| `config/kb_sync.local.json` | **主配置文件**（包含数据库和 Dify 配置） |
| `config/kb_sync.example.json` | 配置模板 |
| `src/law_push/database.py` | 数据库操作模块（第 67-87 行：配置加载） |
| `src/law_push/knowledge_base.py` | 知识库同步模块（第 23-29 行：配置加载） |
| `scripts/verify_kb_config.py` | 配置验证脚本 |

## 故障排查

### 问题 1: 无法连接数据库

```bash
# 检查配置是否正确
python scripts/verify_kb_config.py

# 测试网络连接
ping 数据库IP
telnet 数据库IP 5432
```

### 问题 2: 认证失败

- 检查用户名和密码是否正确
- 确认数据库用户有访问权限
- 检查 pg_hba.conf 配置

### 问题 3: 找不到表

- 确认 schema 和 table 名称正确
- 检查表是否存在：
  ```sql
  SELECT * FROM information_schema.tables 
  WHERE table_schema = 'public' 
  AND table_name = 'tk_r8p0_case';
  ```

### 问题 4: 配置文件无效

```bash
# 验证 JSON 格式
python -m json.tool config/kb_sync.local.json
```

## 总结

数据库配置的**三个关键位置**：

1. **配置文件**: `config/kb_sync.local.json` - 存储数据库连接信息
2. **加载代码**: `src/law_push/database.py:load_config()` - 读取配置
3. **使用代码**: 
   - `src/law_push/database.py:import_csv()` - 导入 CSV
   - `src/law_push/knowledge_base.py:synchronize()` - 同步知识库

所有数据库操作都通过这个配置系统完成，确保了配置的集中管理和一致性。
