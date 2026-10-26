# 运行与维护

## 手动运行

```powershell
conda activate py310
cd D:\File\VSCodeFile\QDHB\Law-Push
python .\run_filter.py 30
```

任务顺序为分类完成、写入输出、CSV 事务入库、提交知识库。
分类失败不覆盖上次成功导出；入库失败保留 CSV；知识库失败保留已入库记录。
只有明确允许分类失败时按来源回退，才使用 `crawl 30 --keep-on-error`。

## 失败重试

```powershell
# 数据库恢复后补导入；重复案例跳过
python .\run_filter.py import-cases
# 补同步所有待同步记录
python .\run_filter.py sync-kb
# 仅检查数量，不调用 Dify
python .\run_filter.py sync-kb --dry-run
```

知识库每批读取最多 100 条，默认处理本次启动时的全部待同步记录；`--limit 100` 可限制本次处理量。
新入库记录默认 `fk_r8p0_sync_kb='是'`、`fk_r8p0_wechat_push='否'`。
同步任务只读取明确标记为 `fk_r8p0_sync_kb='否'` 的记录；成功提交后更新为“是”，失败记录保留“否”。
Dify 接收后异步索引；请在知识库后台查看索引结果。
若请求超时或远端接收后数据库提交失败，重试前核对 `case-<fid>` 文档，避免重复创建。

退出码：`0` 成功，`1` 运行失败或部分同步失败，`2` 参数错误，`130` 用户中断。
应用日志在 `logs/law-push.log`，单文件 10 MiB、保留 5 份备份。
定时任务的标准输出另写 `logs/law_filter_schedule.log`，该重定向日志需按部署环境归档。

## Windows 定时任务

```powershell
# 先检查命令，不注册任务
.\scripts\install_daily_filter.ps1 -PythonExecutable 'D:\File\Anaconda\envs\py310\python.exe' -RunAt '08:30' -DryRun
# 安装或更新任务
.\scripts\install_daily_filter.ps1 -PythonExecutable 'D:\File\Anaconda\envs\py310\python.exe' -RunAt '08:30'
```

任务直接使用解释器绝对路径，不依赖登录后手动激活 Conda。安装脚本以项目根目录作为工作目录。
旧任务如果已指向根目录 `run_filter.py`，仍能继续运行；重新安装后日志路径更新到 `logs/`。
整理目录本身不会注册、启动或删除系统任务。

## Linux / macOS

```bash
source .venv/bin/activate
python3 setup_daily_task.py --time 13:45
```

默认每周六 20:30 执行；安装脚本会直接写入激活环境或项目 `.venv` 的 Python
绝对路径，因此 cron 不需要 `source`。也可用 `--weekday all` 改为每天执行，
或用 `--python /path/to/python` 显式指定。安装前会实际导入 `psycopg`、
`requests`、`bs4` 做预检，依赖缺失会拒绝写入 cron。

也可使用 `scripts/install_daily_filter.sh`，按固定标记更新 cron 条目（该脚本
默认每天 08:00，可通过项目中的 crontab 条目调整）。

## 测试与打包

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m pip wheel . --no-deps --wheel-dir dist
```

测试使用模拟外部服务，不自动爬取、推送或提交知识库。wheel 仅包含业务包，不包含私有配置、输出和归档脚本。
安装 wheel 后设置 `LAW_PUSH_HOME`，在其 `config/` 中部署私有配置，再执行 `law-push check-config`。
