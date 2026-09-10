# 爬取并通过 Dify 智能体分类；result.txt 保存过滤前的全部爬取结果，
# 分类完成后仅生成 law.txt（法律条文）和 case.csv（法律案例）。
python .\run_filter.py 30

# 输出字段顺序：标题、来源、日期、链接、文件日期。
# 日期：爬取记录中的原始日期（网站发布的法律或案例日期）。
# 文件日期：本次输出文件生成时间，格式 YYYY-MM-DD HH:MM:SS，默认使用保存时的本机时间。
# 可指定文件日期，不影响爬取范围和原始记录日期：
python .\run_filter.py 30 --file-date "2026-09-09 17:30:45"
# 推送时保留文件中的时分秒；旧版仅年月日的文件日期补为 00:00:00（实际生成时刻未知）。
# push_case.py 同样支持 --file-date "2026-09-09 17:30:45" 覆盖文件日期。
# TXT 使用 UTF-8，CSV 使用 UTF-8 BOM，便于 Excel 打开中文。

# 过滤并保存后，将 case 推送至金蝶（law 不推送）：
python .\run_filter.py 30 --push-case

# 单独发送已有案例 CSV，不重新爬取或调用 Dify：
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
# 当前接口未提供去重约定，重复运行或重复发送同一文件可能创建重复记录。
# 原定时任务仅保存文件；需推送时在定时任务的 run_filter.py 参数中加入 --push-case。

# 将数据库中 fk_r8p0_sync_kb=“是”的案例同步到 Dify 法律案例知识库：
# 先设置 DB_HOST、DB_NAME、DB_USER、DB_PASSWORD、DIFY_KB_API_KEY，执行：
python .\sync_cases_kb.py --dry-run
python .\sync_cases_kb.py
# 默认表名 r8p0_case、数据集 ID SCSruW9H3bsFMvFxBk1n4eUz；可用 DB_TABLE、
# DIFY_KB_DATASET_ID 覆盖。DIFY_KB_API_KEY 是 Dify API 密钥，不是数据集 ID。
# 只有 Dify 成功接收后才将数据库同步字段更新为“否”；失败记录会保留“是”以便重试。

# Dify 暂时不可用时，明确允许按已有来源继续保存
python .\run_filter.py 30 --keep-on-error

# 定时运行
cd D:\File\VSCodeFile\QDHB\Law-Push
.\install_daily_filter.ps1

# Linux/macOS：安装每天 08:00 的 cron 任务
chmod +x install_daily_filter.sh
./install_daily_filter.sh

# 取消定时运行命令
Unregister-ScheduledTask -TaskName "Law-Push-Filtered-Daily" -Confirm:$false
