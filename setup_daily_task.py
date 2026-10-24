#!/usr/bin/env python
"""
Law-Push 定时任务设置工具
用法：
    python setup_daily_task.py                              # 默认每周六 20:30 执行，爬取 30 天
    python setup_daily_task.py --time 08:30                 # 设置每天 08:30 执行
    python setup_daily_task.py --time 14:00 --days 7        # 每天 14:00 执行，爬取 7 天
    python setup_daily_task.py --weekday saturday           # 每周六 20:30 执行
    python setup_daily_task.py --python .venv/bin/python    # 指定解释器
    python setup_daily_task.py --test                       # 测试但不安装
    python setup_daily_task.py --remove                     # 删除定时任务
    python setup_daily_task.py --status                     # 查看任务状态
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_MODULES = ("psycopg", "requests", "bs4")
DEFAULT_TIME = "20:30"
WEEKDAYS = {
    "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
    "thursday": 4, "friday": 5, "saturday": 6,
}
WEEKDAY_LABELS = {
    "sunday": "日", "monday": "一", "tuesday": "二", "wednesday": "三",
    "thursday": "四", "friday": "五", "saturday": "六",
}


def configure_output():
    """Avoid crashing on consoles that cannot encode status symbols."""
    for stream in (sys.stdout, sys.stderr):
        try:
            "⚙️".encode(stream.encoding or "utf-8")
        except (LookupError, UnicodeEncodeError):
            try:
                stream.reconfigure(errors="replace")
            except (AttributeError, ValueError):
                pass


def get_project_root():
    """获取项目根目录"""
    return Path(__file__).resolve().parent


def _absolute(path):
    """Return an absolute path without resolving executable symlinks."""
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def get_python_executable(explicit=None, project_root=None):
    """Choose the active or project virtualenv, otherwise the current Python."""
    root = Path(project_root or get_project_root())
    if explicit:
        found = shutil.which(explicit)
        candidate = Path(found) if found else Path(explicit).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if not candidate.is_file() and not Path(explicit).is_absolute():
            project_candidate = root / candidate.relative_to(Path.cwd())
            if project_candidate.is_file():
                candidate = project_candidate
        return _absolute(candidate)

    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        virtual_root = Path(virtual_env)
        for relative in ("bin/python", "Scripts/python.exe"):
            candidate = virtual_root / relative
            if candidate.is_file():
                return _absolute(candidate)

    for relative in (
        ".venv/bin/python",
        ".venv/Scripts/python.exe",
        "venv/bin/python",
        "venv/Scripts/python.exe",
        "env/bin/python",
        "env/Scripts/python.exe",
    ):
        candidate = root / relative
        if candidate.is_file():
            return _absolute(candidate)
    return _absolute(sys.executable)


def validate_python_executable(python_exe, project_root):
    """Check that the interpreter can load the dependencies used by the job."""
    python_exe = Path(python_exe)
    if not python_exe.is_file():
        print(f"❌ 找不到 Python 解释器: {python_exe}")
        return False

    check = f'''
import sys
if sys.version_info < (3, 10):
    print("VERSION:{sys.version_info.major}.{sys.version_info.minor}")
    raise SystemExit(3)
try:
    import {', '.join(REQUIRED_MODULES)}
except ModuleNotFoundError as exc:
    print("MISSING:" + str(exc.name))
    raise SystemExit(2)
except Exception as exc:
    print("IMPORT:" + type(exc).__name__ + ": " + str(exc))
    raise SystemExit(4)
'''
    requirements = Path(project_root) / "requirements.txt"
    try:
        result = subprocess.run(
            [str(python_exe), "-c", check],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"❌ Python 解释器无法执行: {python_exe} ({exc})")
        return False

    if result.returncode == 0:
        return True

    details = (result.stdout.strip() or result.stderr.strip())
    if details.startswith("MISSING:"):
        missing = details.split(":", 1)[1]
        print(f"❌ Python 解释器缺少依赖 {missing}: {python_exe}")
        print(f"  请先执行: \"{python_exe}\" -m pip install -r \"{requirements}\"")
    elif details.startswith("VERSION:"):
        version = details.split(":", 1)[1]
        print(f"❌ Python {version} 版本过低，需要 3.10 或更高版本: {python_exe}")
    else:
        print(f"❌ Python 依赖检查失败: {python_exe}")
        print(f"  {details or '命令未返回错误详情'}")
    return False


def select_python_executable(project_root, explicit=None):
    """Resolve and verify the interpreter before writing a scheduled task."""
    python_exe = get_python_executable(explicit, project_root)
    if not validate_python_executable(python_exe, project_root):
        return None
    print(f"  使用 Python: {python_exe}")
    return python_exe


def format_schedule(weekday: str | None, time_str: str) -> str:
    """Describe the selected weekly or daily schedule."""
    if weekday is None:
        return f"每天 {time_str}"
    return f"每周{WEEKDAY_LABELS[weekday]} {time_str}"


def setup_windows_task(time_str: str, days: int = 30, dry_run: bool = False,
                       python=None, weekday: str | None = None):
    """设置 Windows 定时任务"""
    project_root = get_project_root()
    python_exe = select_python_executable(project_root, python)
    if python_exe is None:
        return False
    run_script = project_root / "run_filter.py"
    log_dir = project_root / "logs"
    log_file = log_dir / "law_filter_schedule.log"

    # 确保日志目录存在
    log_dir.mkdir(exist_ok=True)

    task_name = "Law-Push-Filtered-Daily"
    schedule = format_schedule(weekday, time_str)
    if weekday is None:
        trigger_command = f"New-ScheduledTaskTrigger -Daily -At '{time_str}'"
    else:
        trigger_command = (
            "New-ScheduledTaskTrigger -Weekly "
            f"-DaysOfWeek {weekday.capitalize()} -At '{time_str}'")

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
        print(f"  执行时间: {schedule}")
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
$trigger = {trigger_command}
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
    -Description 'Law-Push 每周法律案例爬取任务' `
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
        print(f"  执行时间: {schedule}")
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


def setup_linux_task(time_str: str, days: int = 30, dry_run: bool = False,
                     python=None, weekday: str | None = None):
    """设置 Linux/macOS cron 定时任务"""
    project_root = get_project_root()
    python_exe = select_python_executable(project_root, python)
    if python_exe is None:
        return False
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
    schedule = format_schedule(weekday, time_str)
    day_field = "*" if weekday is None else str(WEEKDAYS[weekday])
    cron_line = (f'{minute} {hour} * * {day_field} cd "{project_root}" && '
                 f'"{python_exe}" -u "{run_script}" {days} >> "{log_file}" 2>&1 {marker}')

    if dry_run:
        print("\n📋 预览配置（不会实际创建任务）：")
        print(f"  执行时间: {schedule}")
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
            print(f"  执行时间: {schedule}")
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
    configure_output()
    parser = argparse.ArgumentParser(
        description="Law-Push 定时任务设置工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python setup_daily_task.py                        默认每周六 20:30 执行，爬取 30 天
  python setup_daily_task.py --time 08:30           每天 08:30 执行，爬取 30 天
  python setup_daily_task.py --time 14:00 --days 7  每天 14:00 执行，爬取 7 天
  python setup_daily_task.py --weekday saturday --time 20:30  每周六 20:30 执行
  python setup_daily_task.py --python .venv/bin/python  指定任务使用的解释器
  python setup_daily_task.py --test                 测试但不安装
  python setup_daily_task.py --status               查看任务状态
  python setup_daily_task.py --remove               删除定时任务
        """
    )

    parser.add_argument(
        "--time",
        default=DEFAULT_TIME,
        help=f"执行时间，格式 HH:MM（默认 {DEFAULT_TIME}）"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="爬取最近多少天的数据（默认 30 天）"
    )
    parser.add_argument(
        "--weekday",
        choices=[*WEEKDAYS, "all"],
        help="每周几执行（默认 saturday）；传入 all 则每天执行"
    )
    parser.add_argument(
        "--python",
        dest="python",
        help="定时任务使用的 Python 解释器（默认优先使用项目 .venv）"
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
    weekday = args.weekday or "saturday"
    if weekday == "all":
        weekday = None

    if system == "Windows":
        success = setup_windows_task(
            args.time, args.days, dry_run=args.test, python=args.python,
            weekday=weekday)
    elif system in ["Linux", "Darwin"]:
        success = setup_linux_task(
            args.time, args.days, dry_run=args.test, python=args.python,
            weekday=weekday)
    else:
        print(f"❌ 不支持的操作系统: {system}")
        return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
