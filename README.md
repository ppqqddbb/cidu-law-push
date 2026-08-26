# 爬取并通过 Dify 智能体分类；result.txt 保存过滤前的全部爬取结果，
# 分类完成后 law.txt 保存法律条文，case.txt 保存法律案例。
python .\run_filter.py 30

# Dify 暂时不可用时，明确允许按已有来源继续保存
python .\run_filter.py 30 --keep-on-error

# 定时运行
cd D:\File\VSCodeFile\QDHB\Law-Push
.\install_daily_filter.ps1

# Linux/macOS：安装每天 08:00 的 cron 任务
chmod +x install_daily_filter.sh
./install_daily_filter.sh
