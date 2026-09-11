# 使用 py310 环境安装运行依赖（先切换到 Law-Push 目录）：
conda activate py310
python -m pip install -r requirements.txt

# 爬取并通过 Dify 智能体分类；result.txt 保存过滤前的全部爬取结果，
# 分类完成后生成 law.txt（法律条文）和 case.csv（法律案例），
# 自动将 case.csv 入库，再将数据库中待同步的案例提交到 Dify 知识库。
python .\run_filter.py 30

# 输出字段顺序：标题、来源、日期、链接、文件日期。
# 日期：爬取记录中的原始日期（网站发布的法律或案例日期）。
# 文件日期：本次输出文件生成时间，格式 YYYY-MM-DD HH:MM:SS，默认使用保存时的本机时间。
# 可指定文件日期，不影响爬取范围和原始记录日期：
python .\run_filter.py 30 --file-date "2026-09-09 17:30:45"
# 推送时保留文件中的时分秒；旧版仅年月日的文件日期补为 00:00:00（实际生成时刻未知）。
# push_case.py 同样支持 --file-date "2026-09-09 17:30:45" 覆盖文件日期。
# TXT 使用 UTF-8，CSV 使用 UTF-8 BOM，便于 Excel 打开中文。

# 一条命令完成：爬取 → Dify 分类 → 生成 CSV → 数据库入库 → Dify 知识库同步。
# case.csv 中的案例写入金蝶数据库，law.txt 不写入案例库：
python .\run_filter.py 30
# 仅入库，暂不提交知识库（记录保持待同步，之后可补同步）：
python .\run_filter.py 30 --no-sync-kb
# 仅生成文件，跳过入库和知识库同步：
python .\run_filter.py 30 --no-push-case

# 数据库配置：复制 kb_sync.example.json 为 kb_sync.local.json，填写 database 部分。
# 本机已经配置。导入端与合同智审 API 必须连接同一个数据库、schema 和 table。
# 可通过 --database-config 指定配置文件，或用 CASE_DB_CONFIG 指定路径。
# CASE_DB_HOST、CASE_DB_PORT、CASE_DB_NAME、CASE_DB_USER、CASE_DB_PASSWORD、
# CASE_DB_SCHEMA、CASE_DB_TABLE 可覆盖对应配置，与合同智审 API 的变量名一致。
# 按标题和链接去重；重复运行自动跳过已有案例。入库失败返回非零退出码，保留 CSV。
# 单独重试已有 CSV 入库，不重新爬取或调用 Dify：
python .\case_database.py .\case.csv
# 入库完成后，单独补同步知识库：
python .\sync_cases_kb.py

# 前端案例库直接通过 API 查询数据库，按文件日期分组，保留标题、来源、日期和原文链接。
# 打开“案例库”或点击“刷新”即可看到最新入库记录，无需上传文件或点击同步按钮。
# 修改代码后需重启后端并刷新前端；安装版需重新打包。

# 以下为兼容旧流程的金蝶 HTTP 推送，不是默认数据库入库方式：
python .\push_case.py .\case.csv

# 金蝶配置：本机 kingdee.local.json 使用本地测试环境认证信息，并被 Git 忽略。
# 在其他机器部署时，将 kingdee.example.json 复制为 kingdee.local.json 并填写认证信息。
# 默认 token 地址：http://127.0.0.1:8881/ierp/kapi/oauth2/getToken
# 案例地址：http://127.0.0.1:8881/ierp/kapi/v2/r8p0/r8p0_law/r8p0_case/case
# 127.0.0.1 指运行此 Python 脚本的机器，可通过配置 case_url 更改。
# token 的 accountId 来自本地配置 account_id，必须属于业务接口对应的数据中心。
# nonce 和 timestamp 每次请求自动生成，无需复制测试时的固定值。
# 请求头使用 access_token；仅配置 identity 时才发送 x-acgw-identity，
# 请填写当前环境的网关身份，不要复用其他环境的值。认证信息及 token 不写入日志。
# 可用 KINGDEE_CONFIG 指定配置路径，或使用 KINGDEE_CLIENT_ID、KINGDEE_CLIENT_SECRET、
# KINGDEE_USERNAME、KINGDEE_ACCOUNT_ID、KINGDEE_IDENTITY、KINGDEE_TOKEN_URL、
# KINGDEE_CASE_URL、KINGDEE_SYNC_KB 环境变量覆盖配置。
# r8p0_sync_kb 默认字符串“是”，可用 --sync-kb 覆盖。
# r8p0_summary 使用记录已有摘要，缺少时传空字符串。
# 标题、来源、链接、日期、文件日期分别对应 r8p0_title、r8p0_source、r8p0_link、
# r8p0_date、r8p0_file_date；请求体为 {"data": [案例记录, ...]}。
# 无案例时跳过请求。HTTP 错误、无效 JSON 或 status 不为 true 时返回非零退出码。
# 推送失败保留已生成的 TXT/CSV，不自动重试写入；超时后先核对金蝶记录再重发。
# 旧金蝶 HTTP 接口未提供去重约定，重复发送同一文件可能创建重复记录。
# 定时任务执行 run_filter.py 时同样会自动入库并同步知识库。

# 数据库与知识库共用 kb_sync.local.json（或 --database-config 指定的文件）。
# database 部分填写数据库连接；dify 部分填写 base_url、api_key、dataset_id。
# 未填写 dataset_id 时，会按 dataset_name 在全部知识库中查找唯一匹配。
# 可用 DIFY_KB_API_KEY、DIFY_KB_BASE_URL、DIFY_KB_DATASET_ID、DIFY_KB_DATASET_NAME 覆盖。
# DIFY_KB_API_KEY 必须是知识库 API 密钥，与爬取分类使用的 DIFY_API_KEY 不同。
# 自动同步所有 fk_r8p0_sync_kb=“是”的案例，包括以前失败的记录，默认不限制为 100 条。
# 仅查看待同步数量（不发送请求、不修改数据库）：
python .\sync_cases_kb.py --dry-run
# 仅重试知识库同步，不重新爬取、不重新入库：
python .\sync_cases_kb.py
# 可选 --limit 100 限制本次处理数；默认处理全部待同步记录。
# Dify 成功返回 document.id 后将同步字段更新为“否”；Dify 随后异步建立索引。
# 失败记录保留“是”，且命令返回非零退出码；CSV 和已入库记录都会保留。
# 已同步记录不重复发送。请求超时或 Dify 接收后数据库提交失败时，
# 先核对知识库中的 case-<fid> 文档再重试，避免远端已接收但本地未确认造成重复。

# Dify 暂时不可用时，明确允许按已有来源继续保存
python .\run_filter.py 30 --keep-on-error

# 定时运行
cd D:\File\VSCodeFile\QDHB\Law-Push
.\install_daily_filter.ps1 -PythonExecutable 'D:\File\Anaconda\envs\py310\python.exe'

# Linux/macOS：安装每天 08:00 的 cron 任务
chmod +x install_daily_filter.sh
./install_daily_filter.sh

# 取消定时运行命令
Unregister-ScheduledTask -TaskName "Law-Push-Filtered-Daily" -Confirm:$false
