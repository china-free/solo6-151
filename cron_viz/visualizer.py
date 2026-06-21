from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict

from .scheduler import ExecutionPoint, ScheduleResult
from .conflict_detector import Conflict, ConflictDetector


class ANSIColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"

    COLORS = [
        "\033[38;5;39m",
        "\033[38;5;208m",
        "\033[38;5;46m",
        "\033[38;5;196m",
        "\033[38;5;213m",
        "\033[38;5;51m",
        "\033[38;5;202m",
        "\033[38;5;42m",
        "\033[38;5;129m",
        "\033[38;5;180m",
    ]

    TASK_MARKERS = ["●", "◆", "▲", "■", "★", "⬢", "◈", "♦", "●", "◆"]

    @staticmethod
    def colorize(text: str, color_code: str, bold: bool = False) -> str:
        prefix = ANSIColor.BOLD + color_code if bold else color_code
        return f"{prefix}{text}{ANSIColor.RESET}"

    @staticmethod
    def get_task_color(index: int) -> str:
        return ANSIColor.COLORS[index % len(ANSIColor.COLORS)]

    @staticmethod
    def get_task_marker(index: int) -> str:
        return ANSIColor.TASK_MARKERS[index % len(ANSIColor.TASK_MARKERS)]


class TimelineVisualizer:
    def __init__(self, width: int = 80, use_color: bool = True):
        self.width = max(width, 60)
        self.use_color = use_color

    def _wrap_color(self, text: str, color_fn) -> str:
        if self.use_color:
            return color_fn(text)
        return text

    def render_header(self, start_time: datetime, end_time: datetime) -> str:
        lines = []
        total_days = (end_time - start_time).days + 1
        range_str = f"{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}"
        title = f" CRON 任务排期时间轴 ({range_str}) "
        pad_len = max(0, self.width - len(title))
        left_pad = pad_len // 2
        right_pad = pad_len - left_pad

        header_line = self._wrap_color(
            "═" * left_pad + title + "═" * right_pad,
            lambda t: ANSIColor.colorize(t, ANSIColor.CYAN, bold=True)
        )
        lines.append(header_line)
        lines.append("")
        return "\n".join(lines)

    def render_task_info(
        self,
        task_names: List[str],
        descriptions: Dict[str, str],
    ) -> str:
        lines = []
        lines.append(
            self._wrap_color("  任务列表:", lambda t: ANSIColor.colorize(t, ANSIColor.BOLD))
        )

        for idx, name in enumerate(task_names):
            marker = ANSIColor.get_task_marker(idx)
            color = ANSIColor.get_task_color(idx)
            colored_marker = self._wrap_color(
                marker, lambda t: ANSIColor.colorize(t, color, bold=True)
            )
            desc = descriptions.get(name, "")
            name_colored = self._wrap_color(
                name, lambda t: ANSIColor.colorize(t, color, bold=True)
            )
            lines.append(f"    {colored_marker} {name_colored}")
            if desc:
                lines.append(
                    f"      "
                    + self._wrap_color(desc, lambda t: ANSIColor.colorize(t, ANSIColor.DIM))
                )
        lines.append("")
        return "\n".join(lines)

    def render_daily_timeline(
        self,
        schedule_results: Dict[str, ScheduleResult],
        conflicts: List[Conflict],
        start_time: datetime,
        end_time: datetime,
    ) -> str:
        lines = []
        task_names = sorted(schedule_results.keys())
        task_colors = {
            name: ANSIColor.get_task_color(i) for i, name in enumerate(task_names)
        }
        task_indices = {name: i for i, name in enumerate(task_names)}
        conflict_minutes = ConflictDetector.get_conflict_minutes(conflicts)

        current_day = start_time.date()
        end_day = end_time.date()

        while current_day <= end_day:
            day_start = datetime.combine(current_day, datetime.min.time())
            day_end = day_start + timedelta(days=1)

            day_title = self._wrap_color(
                f"  ┌─ {current_day.strftime('%Y-%m-%d %A')} ─",
                lambda t: ANSIColor.colorize(t, ANSIColor.BOLD + ANSIColor.WHITE)
            )
            day_title += self._wrap_color(
                "─" * max(0, self.width - len(day_title) - 4) + "┐",
                lambda t: ANSIColor.colorize(t, ANSIColor.DIM)
            )
            lines.append(day_title)

            hour_labels = self._render_hour_axis()
            lines.append(f"  │ {hour_labels}")

            task_lines: Dict[str, List[str]] = defaultdict(list)
            for name in task_names:
                task_lines[name] = [" "] * 24

            for name, result in schedule_results.items():
                for exec_point in result.executions:
                    if day_start <= exec_point.time < day_end:
                        hour = exec_point.time.hour
                        marker = ANSIColor.get_task_marker(task_indices[name])
                        is_conflict = exec_point.minute_key in conflict_minutes
                        if is_conflict:
                            task_lines[name][hour] = self._wrap_color(
                                marker,
                                lambda t: ANSIColor.colorize(
                                    t, ANSIColor.BG_RED + ANSIColor.WHITE, bold=True
                                )
                            )
                        else:
                            task_lines[name][hour] = self._wrap_color(
                                marker,
                                lambda t: ANSIColor.colorize(t, task_colors[name], bold=True)
                            )

            for name in task_names:
                color = task_colors[name]
                row_content = " ".join(task_lines[name])
                task_label = self._wrap_color(
                    name[:18].ljust(18),
                    lambda t: ANSIColor.colorize(t, color, bold=True)
                )
                lines.append(f"  │ {task_label} │ {row_content} ")

            conflict_hours = set()
            for c in conflicts:
                if day_start <= c.time < day_end:
                    conflict_hours.add(c.time.hour)

            if conflict_hours:
                conflict_row = [" "] * 24
                for h in conflict_hours:
                    conflict_row[h] = self._wrap_color(
                        "!",
                        lambda t: ANSIColor.colorize(
                            t, ANSIColor.BG_RED + ANSIColor.WHITE, bold=True
                        )
                    )
                conflict_label = self._wrap_color(
                    "! 冲突检测".ljust(18),
                    lambda t: ANSIColor.colorize(t, ANSIColor.RED, bold=True)
                )
                lines.append(f"  │ {conflict_label} │ {' '.join(conflict_row)} ")

            footer = self._wrap_color(
                "  └" + "─" * (self.width - 4) + "┘",
                lambda t: ANSIColor.colorize(t, ANSIColor.DIM)
            )
            lines.append(footer)
            lines.append("")

            current_day += timedelta(days=1)

        return "\n".join(lines)

    def _render_hour_axis(self) -> str:
        hours = []
        for h in range(24):
            hours.append(f"{h:02d}")
        axis = self._wrap_color(
            " ".join(hours),
            lambda t: ANSIColor.colorize(t, ANSIColor.YELLOW, bold=True)
        )
        label = self._wrap_color(
            "时间轴 (时)".ljust(18),
            lambda t: ANSIColor.colorize(t, ANSIColor.YELLOW, bold=True)
        )
        return f"{label} │ {axis} "

    def render_conflicts(self, conflicts: List[Conflict]) -> str:
        if not conflicts:
            ok_msg = self._wrap_color(
                "  [OK] 没有检测到任务冲突！",
                lambda t: ANSIColor.colorize(t, ANSIColor.GREEN, bold=True)
            )
            return ok_msg + "\n"

        lines = []
        lines.append(
            self._wrap_color(
                f"  [!] 检测到 {len(conflicts)} 个时间冲突:",
                lambda t: ANSIColor.colorize(t, ANSIColor.RED, bold=True)
            )
        )

        summary = ConflictDetector.summarize(conflicts)

        sev_colors = {
            "CRITICAL": ANSIColor.BG_RED + ANSIColor.WHITE,
            "HIGH": ANSIColor.RED,
            "MEDIUM": ANSIColor.YELLOW,
            "LOW": ANSIColor.CYAN,
        }

        lines.append("")
        lines.append(
            "    "
            + self._wrap_color("严重程度:", lambda t: ANSIColor.colorize(t, ANSIColor.BOLD))
        )
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            count = summary["by_severity"][sev]
            if count > 0:
                sev_label = self._wrap_color(
                    f"[{sev}]",
                    lambda t: ANSIColor.colorize(t, sev_colors[sev], bold=True)
                )
                lines.append(f"      {sev_label} {count} 个")

        lines.append("")
        lines.append(
            "    "
            + self._wrap_color("冲突详情:", lambda t: ANSIColor.colorize(t, ANSIColor.BOLD))
        )

        for idx, c in enumerate(conflicts[:50]):
            sev_color = sev_colors[c.severity]
            sev_label = self._wrap_color(
                f"[{c.severity}]",
                lambda t: ANSIColor.colorize(t, sev_color, bold=True)
            )
            time_str = c.time.strftime("%Y-%m-%d %H:%M")
            time_colored = self._wrap_color(
                time_str, lambda t: ANSIColor.colorize(t, ANSIColor.BOLD)
            )
            task_list = ", ".join(c.tasks)
            lines.append(
                f"      {idx + 1:>3}. {sev_label} {time_colored} - {task_list}"
            )

        if len(conflicts) > 50:
            lines.append(
                self._wrap_color(
                    f"      ... 还有 {len(conflicts) - 50} 个冲突未显示",
                    lambda t: ANSIColor.colorize(t, ANSIColor.DIM)
                )
            )

        lines.append("")
        return "\n".join(lines)

    def render_statistics(
        self, schedule_results: Dict[str, ScheduleResult]
    ) -> str:
        lines = []
        lines.append(
            self._wrap_color(
                "  [统计] 执行统计:",
                lambda t: ANSIColor.colorize(t, ANSIColor.BOLD)
            )
        )

        total = 0
        for name, result in sorted(schedule_results.items()):
            color = ANSIColor.get_task_color(
                list(schedule_results.keys()).index(name)
            )
            name_colored = self._wrap_color(
                name, lambda t: ANSIColor.colorize(t, color, bold=True)
            )
            lines.append(
                f"    {name_colored}: {result.count} 次执行"
            )
            total += result.count

        lines.append(
            self._wrap_color(
                f"    {'─' * 30}",
                lambda t: ANSIColor.colorize(t, ANSIColor.DIM)
            )
        )
        lines.append(
            self._wrap_color(
                f"    合计: {total} 次执行",
                lambda t: ANSIColor.colorize(t, ANSIColor.BOLD)
            )
        )
        lines.append("")
        return "\n".join(lines)

    def render_hourly_detail(
        self,
        schedule_results: Dict[str, ScheduleResult],
        conflicts: List[Conflict],
        start_time: datetime,
        end_time: datetime,
    ) -> str:
        lines = []
        task_names = sorted(schedule_results.keys())
        task_colors = {
            name: ANSIColor.get_task_color(i) for i, name in enumerate(task_names)
        }
        task_indices = {name: i for i, name in enumerate(task_names)}
        conflict_minutes = ConflictDetector.get_conflict_minutes(conflicts)

        lines.append(
            self._wrap_color(
                "  每小时详细视图 (分钟级):",
                lambda t: ANSIColor.colorize(t, ANSIColor.BOLD)
            )
        )
        lines.append("")

        all_execs = []
        for result in schedule_results.values():
            all_execs.extend(result.executions)
        all_execs.sort()

        if not all_execs:
            lines.append("    (无执行记录)")
            lines.append("")
            return "\n".join(lines)

        current_hour = None
        for exec_point in all_execs:
            hour_key = exec_point.time.strftime("%Y-%m-%d %H:00")
            if hour_key != current_hour:
                current_hour = hour_key
                lines.append(
                    self._wrap_color(
                        f"  ┌─ {hour_key} ─" + "─" * 30,
                        lambda t: ANSIColor.colorize(t, ANSIColor.BLUE, bold=True)
                    )
                )

            minute = exec_point.time.minute
            name = exec_point.cron_expr.name if exec_point.cron_expr.name else str(
                exec_point.cron_expr
            )
            color = task_colors.get(name, ANSIColor.WHITE)
            marker = ANSIColor.get_task_marker(task_indices.get(name, 0))
            is_conflict = exec_point.minute_key in conflict_minutes

            minute_bar = [" "] * 60
            if is_conflict:
                minute_bar[minute] = self._wrap_color(
                    marker,
                    lambda t: ANSIColor.colorize(
                        t, ANSIColor.BG_RED + ANSIColor.WHITE, bold=True
                    )
                )
            else:
                minute_bar[minute] = self._wrap_color(
                    marker,
                    lambda t: ANSIColor.colorize(t, color, bold=True)
                )

            bar_display = ""
            for i in range(0, 60, 5):
                chunk = "".join(minute_bar[i:i + 5])
                bar_display += chunk + " "

            time_str = f"{minute:02d}分"
            lines.append(
                f"  │ {self._wrap_color(time_str, lambda t: ANSIColor.colorize(t, ANSIColor.DIM))} {bar_display.strip()}"
            )

        lines.append("")
        return "\n".join(lines)

    def render_legend(self) -> str:
        lines = []
        lines.append(
            self._wrap_color("  图例:", lambda t: ANSIColor.colorize(t, ANSIColor.BOLD))
        )

        legend_items = []
        for i, marker in enumerate(ANSIColor.TASK_MARKERS[:5]):
            colored = self._wrap_color(
                marker,
                lambda t: ANSIColor.colorize(t, ANSIColor.get_task_color(i), bold=True)
            )
            legend_items.append(f"{colored} 任务执行点")

        conflict_marker = self._wrap_color(
            "●",
            lambda t: ANSIColor.colorize(
                t, ANSIColor.BG_RED + ANSIColor.WHITE, bold=True
            )
        )
        legend_items.append(f"{conflict_marker} 冲突")

        lines.append("    " + "  ".join(legend_items))
        lines.append("")
        return "\n".join(lines)
