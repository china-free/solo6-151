#!/usr/bin/env python3
import argparse
import sys
import os
import io
from datetime import datetime, timedelta
from typing import List, Tuple, Dict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from cron_viz import (
    CronParser,
    CronExpression,
    CronScheduler,
    TimelineVisualizer,
    ConflictDetector,
)
from cron_viz.scheduler import ScheduleResult


def _is_cron_field(text: str) -> bool:
    if not text:
        return False
    if text == "*":
        return True
    if "=" in text and not text.split("=", 1)[0].replace("*/", "").replace("/", "").isdigit():
        return False
    cleaned = text.replace("*/", "").replace("*", "").replace("/", "").replace("-", "").replace(",", "")
    if not cleaned:
        return True
    return cleaned.isdigit()


def parse_cron_args(args_list: List[str]) -> List[Tuple[str, str]]:
    result = []
    i = 0
    task_counter = 0

    while i < len(args_list):
        arg = args_list[i]

        if arg.startswith("-"):
            i += 1
            continue

        if "=" in arg and not _is_cron_field(arg.split("=", 1)[0]):
            name, expr_part = arg.split("=", 1)
            expr_fields = [expr_part]
            i += 1
            while i < len(args_list) and len(expr_fields) < 5 and _is_cron_field(args_list[i]):
                expr_fields.append(args_list[i])
                i += 1
            expr = " ".join(expr_fields)
            if len(expr_fields) == 5:
                task_counter += 1
                result.append((name.strip(), expr.strip()))
            continue

        if _is_cron_field(arg):
            expr_fields = [arg]
            j = i + 1
            while j < len(args_list) and len(expr_fields) < 5 and _is_cron_field(args_list[j]):
                expr_fields.append(args_list[j])
                j += 1

            if len(expr_fields) == 5:
                expr = " ".join(expr_fields)
                name = None
                if j < len(args_list) and not args_list[j].startswith("-") and not _is_cron_field(args_list[j]):
                    name = args_list[j]
                    j += 1
                task_counter += 1
                if not name:
                    name = f"task_{task_counter}"
                result.append((name, expr))
                i = j
                continue

        i += 1

    return result


def read_tasks_from_file(filepath: str) -> List[Tuple[str, str]]:
    tasks = []
    if not os.path.exists(filepath):
        print(f"错误: 文件不存在: {filepath}", file=sys.stderr)
        return tasks

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 5)
            if len(parts) >= 5:
                cron_fields = parts[:5]
                cron_expr = " ".join(cron_fields)
                name = parts[5] if len(parts) > 5 else f"line_{line_num}"
                tasks.append((name.strip(), cron_expr.strip()))
            elif "=" in line:
                name, expr = line.split("=", 1)
                tasks.append((name.strip(), expr.strip()))
            else:
                print(f"警告: 第 {line_num} 行格式无法识别，已跳过: {line}", file=sys.stderr)
    return tasks


def format_task_table(expressions: List[CronExpression]) -> str:
    lines = []
    lines.append("  ┌──────────────────────────────────────────────────────────────────────────────┐")
    lines.append("  │                            Cron 表达式解析结果                               │")
    lines.append("  ├────────────────────┬───────────────────────┬──────────────────────────────────┤")
    lines.append("  │ 任务名称            │ Cron 表达式           │ 自然语言描述                     │")
    lines.append("  ├────────────────────┼───────────────────────┼──────────────────────────────────┤")

    for expr in expressions:
        name = expr.name if expr.name else "(未命名)"
        cron_str = str(expr)
        human_readable = CronParser.to_human_readable(expr)

        name_display = name[:18]
        cron_display = cron_str[:21]
        desc_display = human_readable[:32]

        lines.append(
            f"  │ {name_display:<18} │ {cron_display:<21} │ {desc_display:<32} │"
        )

    lines.append("  └────────────────────┴───────────────────────┴──────────────────────────────────┘")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Cron 任务排期推演工具 - 可视化未来执行时间并检测冲突",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s "*/15 * * * *" 数据同步
  %(prog)s --days 3 "0 2 * * *=数据库备份" "0,30 * * * *=日志采集"
  %(prog)s -f tasks.txt --detail
  %(prog)s "0 8 * * 1-5=工作日晨会" "0 9 * * 0,6=周末巡检"
        """,
    )

    parser.add_argument(
        "tasks",
        nargs="*",
        help="Cron 任务，格式: [名称=]表达式 或 表达式 [名称]",
    )

    parser.add_argument(
        "-f", "--file",
        metavar="FILE",
        help="从文件读取任务列表，每行一个任务，格式: 分 时 日 月 周 [名称] 或 名称=表达式",
    )

    parser.add_argument(
        "-d", "--days",
        type=int,
        default=7,
        help="推演的天数 (默认: 7)",
    )

    parser.add_argument(
        "--start",
        metavar="DATETIME",
        help="开始时间，格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM (默认: 现在)",
    )

    parser.add_argument(
        "--end",
        metavar="DATETIME",
        help="结束时间，格式: YYYY-MM-DD 或 YYYY-MM-DD HH:MM (默认: start + days)",
    )

    parser.add_argument(
        "--width",
        type=int,
        default=100,
        help="输出宽度 (默认: 100)",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="禁用彩色输出",
    )

    parser.add_argument(
        "--detail",
        action="store_true",
        help="显示详细的分钟级时间轴",
    )

    parser.add_argument(
        "--no-timeline",
        action="store_true",
        help="不显示每日时间轴，只显示冲突检测结果",
    )

    args = parser.parse_args()

    task_specs: List[Tuple[str, str]] = []

    if args.file:
        file_tasks = read_tasks_from_file(args.file)
        task_specs.extend(file_tasks)

    if args.tasks:
        arg_tasks = parse_cron_args(args.tasks)
        task_specs.extend(arg_tasks)

    if not task_specs:
        parser.print_help()
        print("\n错误: 请至少指定一个 Cron 任务", file=sys.stderr)
        sys.exit(1)

    expressions: List[CronExpression] = []
    for name, expr_str in task_specs:
        try:
            expr = CronParser.parse(expr_str, name=name)
            expressions.append(expr)
        except ValueError as e:
            print(f"错误: 任务 '{name}' 解析失败: {e}", file=sys.stderr)
            sys.exit(1)

    print("\n" + format_task_table(expressions) + "\n")

    start_time = None
    end_time = None

    if args.start:
        try:
            if len(args.start) <= 10:
                start_time = datetime.strptime(args.start, "%Y-%m-%d")
            else:
                start_time = datetime.strptime(args.start, "%Y-%m-%d %H:%M")
        except ValueError:
            print(f"错误: 开始时间格式无效: {args.start}", file=sys.stderr)
            sys.exit(1)

    if args.end:
        try:
            if len(args.end) <= 10:
                end_time = datetime.strptime(args.end, "%Y-%m-%d")
            else:
                end_time = datetime.strptime(args.end, "%Y-%m-%d %H:%M")
        except ValueError:
            print(f"错误: 结束时间格式无效: {args.end}", file=sys.stderr)
            sys.exit(1)

    if start_time is None:
        start_time = datetime.now().replace(second=0, microsecond=0)
    if end_time is None:
        end_time = start_time + timedelta(days=args.days)

    visualizer = TimelineVisualizer(width=args.width, use_color=not args.no_color)

    print(visualizer.render_header(start_time, end_time))

    schedule_results: Dict[str, ScheduleResult] = {}
    for expr in expressions:
        key = expr.name if expr.name else str(expr)
        try:
            schedule_results[key] = CronScheduler.calculate_executions(
                expr, start_time=start_time, end_time=end_time
            )
        except Exception as e:
            print(f"错误: 计算任务 '{key}' 排期失败: {e}", file=sys.stderr)
            sys.exit(1)

    task_names = sorted(schedule_results.keys())

    descriptions = {}
    for expr in expressions:
        key = expr.name if expr.name else str(expr)
        descriptions[key] = CronParser.to_human_readable(expr)

    print(visualizer.render_task_info(task_names, descriptions))

    if not args.no_timeline:
        conflicts = ConflictDetector.detect(schedule_results)
        print(visualizer.render_daily_timeline(
            schedule_results, conflicts, start_time, end_time
        ))

        if args.detail:
            print(visualizer.render_hourly_detail(
                schedule_results, conflicts, start_time, end_time
            ))

    print(visualizer.render_statistics(schedule_results))

    conflicts = ConflictDetector.detect(schedule_results)
    print(visualizer.render_conflicts(conflicts))

    print(visualizer.render_legend())

    summary = ConflictDetector.summarize(conflicts)
    if summary["total_conflicts"] > 0:
        print(
            f"  [提示] 共有 {summary['total_conflicts']} 个冲突点，"
            f"最多同时有 {summary['max_tasks_at_once']} 个任务撞车。"
            f"建议调整任务执行时间以错开高峰。"
        )
    print()


if __name__ == "__main__":
    main()
