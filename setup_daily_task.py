#!/usr/bin/env python
"""
Law-Push 定时任务设置工具
用法：
    python setup_daily_task.py                              # 默认每天 08:00 执行，爬取 30 天
    python setup_daily_task.py --time 08:30                 # 设置每天 08:30 执行
    python setup_daily_task.py --time 14:00 --days 7        # 每天 14:00 执行，爬取 7 天
    python setup_daily_task.py --test                       # 测试但不安装
    python setup_daily_task.py --remove                     # 删除定时任务
    python setup_daily_task.py --status                     # 查看任务状态
"""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


def get_project_root():
    """获取项目根目录"""
    return Path(__file__).resolve().parent


def get_python_executable():
    """获取当前 Python 解释器的绝对路径"""
    return sys.executable


def setup_windows_task(time_str: str, days: int = 30, dry_run: bool = False):
    """设置 Windows 定时任务"""
    project_root = get_project_root()
    python_exe = get_python_executable()
    run_script = project_root / "run_filter.py"
    log_dir = project_root / "logs"
    log_file = log_dir / "law_filter_schedule.log"

    # 确保日志目录存在
    log_dir.mkdir(exist_ok=True)

    task_name = "Law-Push-Filtered-Daily"

    # 验证时间格式
    try:
        hour, minute = time_str.split(":")
        if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        print(f"❌ 错误：时间格式不正确，应为 HH:MM 格式（如 08:30）")
        return False

    if not run_script.exists():
        print(f"❌ 错误：找不到 run_filter.py 文件")
        return False

    command_line = f'"{python_exe}" -u "{run_script}" {days} >> "{log_file}" 2>&1'

    if dry_run:
        print("\n📋 预览配置（不会实际创建任务）：")
        print(f"  任务名称: {task_name}")
        print(f"  执行时间: 每天 {time_str}")
        print(f"  爬取天数: {days} 天")
        print(f"  Python路径: {python_exe}")
        print(f"  工作目录: {project_root}")
        print(f"  执行命令: python run_filter.py {days}")
        print(f"  日志文件: {log_file}")
        return True

    # 使用 PowerShell 创建定时任务
    ps_script = f'''
$ErrorActionPreference = "Stop"
$action = New-ScheduledTaskAction `
    -Execute '{os.environ.get("ComSpec", "cmd.exe")}' `
    -Argument '/d /c "{command_line}"' `
    -WorkingDirectory '{project_root}'
$trigger = New-ScheduledTaskTrigger -Daily -At '{time_str}'
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName '{task_name}' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description 'Law-Push 每日法律案例爬取任务' `
    -Force | Out-Null
Write-Host "✓"
'''

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"\n✅ 定时任务创建成功！")
        print(f"  任务名称: {task_name}")
        print(f"  执行时间: 每天 {time_str}")
        print(f"  爬取天数: {days} 天")
        print(f"  日志文件: {log_file}")
        print(f"\n💡 管理任务：")
        print(f"  立即测试运行: Start-ScheduledTask -TaskName '{task_name}'")
        print(f"  查看任务状态: Get-ScheduledTask -TaskName '{task_name}'")
        print(f"  删除任务: python {Path(__file__).name} --remove")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 创建任务失败：{e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ 错误：找不到 PowerShell，请确保在 Windows 系统上运行")
        return False


def setup_linux_task(time_str: str, days: int = 30, dry_run: bool = False):
    """设置 Linux/macOS cron 定时任务"""
    project_root = get_project_root()
    python_exe = get_python_executable()
    run_script = project_root / "run_filter.py"
    log_dir = project_root / "logs"
    log_file = log_dir / "law_filter_schedule.log"

    # 确保日志目录存在
    log_dir.mkdir(exist_ok=True)

    # 验证时间格式并转换为 cron 格式
    try:
        hour, minute = time_str.split(":")
        hour, minute = int(hour), int(minute)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        print(f"❌ 错误：时间格式不正确，应为 HH:MM 格式（如 08:30）")
        return False

    if not run_script.exists():
        print(f"❌ 错误：找不到 run_filter.py 文件")
        return False

    marker = "# Law-Push filtered crawl"
    cron_line = f'{minute} {hour} * * * cd "{project_root}" && "{python_exe}" -u "{run_script}" {days} >> "{log_file}" 2>&1 {marker}'

    if dry_run:
        print("\n📋 预览配置（不会实际创建任务）：")
        print(f"  执行时间: 每天 {time_str}")
        print(f"  爬取天数: {days} 天")
        print(f"  Python路径: {python_exe}")
        print(f"  工作目录: {project_root}")
        print(f"  执行命令: python run_filter.py {days}")
        print(f"  日志文件: {log_file}")
        print(f"\nCron 表达式: {cron_line}")
        return True

    try:
        # 读取现有 crontab
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True
        )
        current_crontab = result.stdout if result.returncode == 0 else ""

        # 更新或添加任务
        lines = current_crontab.strip().split('\n') if current_crontab.strip() else []
        new_lines = []
        found = False

        for line in lines:
            if marker in line:
                new_lines.append(cron_line)
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(cron_line)

        new_crontab = '\n'.join(new_lines) + '\n'

        # 安装新的 crontab
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            text=True,
            capture_output=True
        )

        if proc.returncode == 0:
            print(f"\n✅ Cron 定时任务创建成功！")
            print(f"  执行时间: 每天 {time_str}")
            print(f"  爬取天数: {days} 天")
            print(f"  日志文件: {log_file}")
            print(f"\n💡 管理任务：")
            print(f"  查看所有任务: crontab -l")
            print(f"  编辑任务: crontab -e")
            print(f"  删除任务: python {Path(__file__).name} --remove")
            return True
        else:
            print(f"❌ 创建任务失败：{proc.stderr}")
            return False

    except FileNotFoundError:
        print("❌ 错误：找不到 crontab 命令，请确保系统支持 cron")
        return False
    except Exception as e:
        print(f"❌ 创建任务失败：{e}")
        return False


def remove_windows_task():
    """删除 Windows 定时任务"""
    task_name = "Law-Push-Filtered-Daily"

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"✅ 已删除定时任务: {task_name}")
            return True
        else:
            if "No MSFT_ScheduledTask objects found" in result.stderr:
                print(f"ℹ️  任务不存在: {task_name}")
            else:
                print(f"❌ 删除失败：{result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 删除失败：{e}")
        return False


def remove_linux_task():
    """删除 Linux/macOS cron 定时任务"""
    marker = "# Law-Push filtered crawl"

    try:
        # 读取现有 crontab
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("ℹ️  当前没有 cron 任务")
            return True

        current_crontab = result.stdout
        lines = current_crontab.strip().split('\n') if current_crontab.strip() else []

        # 过滤掉包含标记的行
        new_lines = [line for line in lines if marker not in line]

        if len(new_lines) == len(lines):
            print("ℹ️  未找到 Law-Push 定时任务")
            return True

        # 安装新的 crontab
        new_crontab = '\n'.join(new_lines) + '\n' if new_lines else ''
        proc = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            text=True,
            capture_output=True
        )

        if proc.returncode == 0:
            print("✅ 已删除 Law-Push cron 定时任务")
            return True
        else:
            print(f"❌ 删除失败：{proc.stderr}")
            return False

    except Exception as e:
        print(f"❌ 删除失败：{e}")
        return False


def check_windows_status():
    """检查 Windows 定时任务状态"""
    task_name = "Law-Push-Filtered-Daily"

    ps_script = f'''
$task = Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue
if ($task) {{
    $info = Get-ScheduledTaskInfo -TaskName '{task_name}'
    Write-Host "任务名称: {task_name}"
    Write-Host "状态: $($task.State)"
    Write-Host "上次运行: $($info.LastRunTime)"
    Write-Host "下次运行: $($info.NextRunTime)"
    Write-Host "上次结果: $($info.LastTaskResult)"
}} else {{
    Write-Host "未找到任务"
}}
'''

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=False
        )
        print(result.stdout)
    except Exception as e:
        print(f"❌ 查询失败：{e}")


def check_linux_status():
    """检查 Linux/macOS cron 定时任务状态"""
    marker = "# Law-Push filtered crawl"

    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("ℹ️  当前没有 cron 任务")
            return

        found = False
        for line in result.stdout.split('\n'):
            if marker in line:
                print("✅ 找到 Law-Push 定时任务:")
                print(f"  {line}")
                found = True

        if not found:
            print("ℹ️  未找到 Law-Push 定时任务")
    except Exception as e:
        print(f"❌ 查询失败：{e}")


def main():
    parser = argparse.ArgumentParser(
        description="Law-Push 定时任务设置工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python setup_daily_task.py                        默认每天 08:00 执行，爬取 30 天
  python setup_daily_task.py --time 08:30           每天 08:30 执行，爬取 30 天
  python setup_daily_task.py --time 14:00 --days 7  每天 14:00 执行，爬取 7 天
  python setup_daily_task.py --test                 测试但不安装
  python setup_daily_task.py --status               查看任务状态
  python setup_daily_task.py --remove               删除定时任务
        """
    )

    parser.add_argument(
        "--time",
        default="08:00",
        help="每天执行的时间，格式 HH:MM（默认 08:00）"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="爬取最近多少天的数据（默认 30 天）"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="仅测试配置，不实际创建任务"
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="删除已创建的定时任务"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="查看定时任务状态"
    )

    args = parser.parse_args()

    system = platform.system()

    # 查看状态
    if args.status:
        print(f"\n📊 定时任务状态 ({system}):\n")
        if system == "Windows":
            check_windows_status()
        else:
            check_linux_status()
        return 0

    # 删除任务
    if args.remove:
        print(f"\n🗑️  删除定时任务 ({system})...\n")
        if system == "Windows":
            success = remove_windows_task()
        else:
            success = remove_linux_task()
        return 0 if success else 1

    # 创建任务
    print(f"\n⚙️  设置定时任务 ({system})...\n")

    if system == "Windows":
        success = setup_windows_task(args.time, args.days, dry_run=args.test)
    elif system in ["Linux", "Darwin"]:
        success = setup_linux_task(args.time, args.days, dry_run=args.test)
    else:
        print(f"❌ 不支持的操作系统: {system}")
        return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
