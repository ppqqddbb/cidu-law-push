# 数据库配置位置速查

## 📍 配置文件位置

```
config/kb_sync.local.json  ← 主配置文件（数据库 IP、名称、用户名、密码都在这里）
```

### 配置内容示例

```json
{
  "database": {
    "host": "127.0.0.1",           ← 数据库 IP 地址
    "port": 5432,                  ← 数据库端口
    "database": "dev_local_4_all", ← 数据库名称
    "user": "postgres",            ← 数据库用户名
    "password": "020513wyt",       ← 数据库密码
    "schema": "public",            ← 数据库模式
    "table": "tk_r8p0_case"       ← 案例表名
  }
}
```

## 📂 代码位置

### 1️⃣ 加载配置的代码

```
src/law_push/database.py
  ├─ 第 67 行: load_config() 函数定义
  ├─ 第 68 行: 读取配置文件路径
  ├─ 第 73 行: 解析 JSON 中的 database 配置
  └─ 第 78-82 行: 支持环境变量覆盖
```

### 2️⃣ 使用配置的代码

#### 导入 CSV 到数据库
```
src/law_push/database.py
  ├─ 第 95 行: 调用 load_config() 加载配置
  └─ 第 96-99 行: 使用配置建立数据库连接
```

#### 同步到知识库
```
src/law_push/knowledge_base.py
  ├─ 第 17 行: 导入 load_config 函数
  ├─ 第 29 行: 加载数据库配置
  └─ 第 133-136 行: 使用配置连接数据库
```

## 🔧 修改配置的步骤

```bash
# 1. 编辑配置文件
notepad config\kb_sync.local.json

# 2. 修改数据库参数（IP、名称、用户名、密码等）

# 3. 验证配置
python scripts\verify_kb_config.py

# 4. 测试连接
python run_filter.py sync-kb --dry-run
```

## 🌍 环境变量配置（可选）

也可以通过环境变量覆盖配置文件：

```bash
export CASE_DB_HOST=192.168.1.100      # 数据库 IP
export CASE_DB_PORT=5432               # 端口
export CASE_DB_NAME=my_database        # 数据库名
export CASE_DB_USER=myuser             # 用户名
export CASE_DB_PASSWORD=mypassword     # 密码
export CASE_DB_SCHEMA=public           # 模式
export CASE_DB_TABLE=tk_r8p0_case      # 表名
```

## 📊 配置优先级

```
环境变量 > JSON 配置文件
```

## 🔍 快速定位

| 需求 | 位置 |
|------|------|
| **修改数据库 IP** | `config/kb_sync.local.json` → `database.host` |
| **修改数据库名称** | `config/kb_sync.local.json` → `database.database` |
| **修改用户名** | `config/kb_sync.local.json` → `database.user` |
| **修改密码** | `config/kb_sync.local.json` → `database.password` |
| **修改表名** | `config/kb_sync.local.json` → `database.table` |
| **查看配置加载代码** | `src/law_push/database.py:67` |
| **查看数据库连接代码** | `src/law_push/database.py:96`<br>`src/law_push/knowledge_base.py:133` |

## 📚 详细文档

完整说明请参考：[DATABASE_CONFIG_GUIDE.md](DATABASE_CONFIG_GUIDE.md)
