# 目录迁移说明

本次整理保留 `python run_filter.py 30`，该文件现在只负责加载包和转发命令。
其他功能统一通过该入口的子命令或安装后的 `law-push` 执行。

| 原文件 / 命令 | 新位置 / 命令 |
| --- | --- |
| 根目录 `run_filter.py` 的业务代码 | `src/law_push/pipeline.py` 与 `classifier.py` |
| `law_crawler.py` | `src/law_push/crawler.py` |
| `config.py` | `src/law_push/settings.py`、`paths.py` |
| 源码中的分类 API 密钥 | `config/app.local.json`，已保留本机原值 |
| `case_database.py case.csv` | `python run_filter.py import-cases` |
| `sync_cases_kb.py` | `python run_filter.py sync-kb` |
| `push_case.py case.csv` | `python run_filter.py push-kingdee data/output/case.csv` |
| `kingdee_case.py` / `file_dates.py` | `src/law_push/kingdee.py` / `file_dates.py` |
| 根目录 `*.local.json` / `*.example.json` | `config/` |
| 根目录 `case.csv`、`law.txt`、`result.txt` | `data/output/` |
| 根目录定时任务安装脚本 | `scripts/` |
| 旧 `run.py` / `law_filter.py` | `archive/legacy/`，仅供追溯 |

如外部脚本显式设置了 `CASE_DB_CONFIG`、`KINGDEE_CONFIG`，或读取旧的根目录 CSV 路径，
需要更新到新位置。环境变量指定的路径不会被自动改写。
现有旧任务日志 `.run/`、虚拟环境及 IDE 目录保留原样；新应用日志写入 `logs/`。
前端通过数据库查询，输出文件位置变化不影响案例展示。

旧根目录模块不再作为 Python 导入接口；自动化测试已改为导入 `law_push` 包。
后续增加功能应扩展包模块及 `cli.py` 的子命令，避免继续增加根目录脚本。
