from dataclasses import dataclass, field
from typing import List, Set, Optional

from .formatter import (
    MinuteFormatter,
    HourFormatter,
    DayOfMonthFormatter,
    MonthFormatter,
    DayOfWeekFormatter,
)


@dataclass
class CronExpression:
    raw: str
    minute: str
    hour: str
    day_of_month: str
    month: str
    day_of_week: str
    name: str = ""

    def __str__(self) -> str:
        return f"{self.minute} {self.hour} {self.day_of_month} {self.month} {self.day_of_week}"


class CronParser:

    @staticmethod
    def parse(expression: str, name: str = "") -> CronExpression:
        expression = expression.strip()
        parts = expression.split()
        if len(parts) < 5:
            raise ValueError(
                f"Invalid cron expression: '{expression}'. "
                f"Expected 5 fields (minute hour day-of-month month day-of-week), got {len(parts)}"
            )
        return CronExpression(
            raw=expression,
            minute=parts[0],
            hour=parts[1],
            day_of_month=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            name=name,
        )

    @staticmethod
    def _parse_field_values(field: str, min_val: int, max_val: int) -> Set[int]:
        from .formatter import parse_field_values
        return parse_field_values(field, min_val, max_val)

    @staticmethod
    def describe_minute(field: str) -> str:
        return MinuteFormatter.format(field)

    @staticmethod
    def describe_hour(field: str) -> str:
        return HourFormatter.format(field)

    @staticmethod
    def describe_day_of_month(field: str) -> str:
        return DayOfMonthFormatter.format(field)

    @staticmethod
    def describe_month(field: str) -> str:
        return MonthFormatter.format(field)

    @staticmethod
    def describe_day_of_week(field: str) -> str:
        return DayOfWeekFormatter.format(field)

    @staticmethod
    def to_human_readable(expr: CronExpression) -> str:
        minute_field = expr.minute
        hour_field = expr.hour
        dom_field = expr.day_of_month
        month_field = expr.month
        dow_field = expr.day_of_week

        from .formatter import MinuteFormatter, HourFormatter

        minute_analysis = MinuteFormatter.analyze(minute_field)
        hour_analysis = HourFormatter.analyze(hour_field)

        dom_desc = DayOfMonthFormatter.format(dom_field)
        dow_desc = DayOfWeekFormatter.format(dow_field)
        month_desc = MonthFormatter.format(month_field)

        freq_parts = []
        if month_desc:
            freq_parts.append(month_desc)

        if dom_desc and dow_desc:
            freq_parts.append(f"{dom_desc}以及{dow_desc}")
        elif dom_desc:
            freq_parts.append(dom_desc)
        elif dow_desc:
            freq_parts.append(dow_desc)

        if not freq_parts:
            freq_parts.append("每天")

        freq_str = "".join(freq_parts)

        min_wild = minute_analysis.type == "WILDCARD"
        hour_wild = hour_analysis.type == "WILDCARD"
        min_step = minute_analysis.type in ("STEP_ALL", "STEP_RANGE", "STEP_FROM")
        hour_step = hour_analysis.type in ("STEP_ALL", "STEP_RANGE", "STEP_FROM")
        min_single = minute_analysis.type == "SINGLE"
        hour_single = hour_analysis.type == "SINGLE"
        min_list = minute_analysis.type == "LIST"
        hour_list = hour_analysis.type == "LIST"

        if min_wild and hour_wild:
            return f"{freq_str}每分钟执行"

        if min_step and hour_wild:
            minute_desc = MinuteFormatter.format(minute_field)
            return f"{freq_str}{minute_desc}执行"

        if min_wild and hour_step:
            hour_desc = HourFormatter.format(hour_field)
            return f"{freq_str}{hour_desc}每分钟执行"

        if min_step and hour_step:
            minute_desc = MinuteFormatter.format(minute_field)
            hour_desc = HourFormatter.format(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        if min_single and hour_single:
            m = list(minute_analysis.values)[0]
            h = list(hour_analysis.values)[0]
            period, h12 = HourFormatter.format_simple(h)
            if m == 0:
                time_str = f"{period}{h12}点整"
            elif m == 30:
                time_str = f"{period}{h12}点半"
            else:
                time_str = f"{period}{h12}点{m:02d}分"
            return f"{freq_str}{time_str}执行"

        if min_list and hour_single:
            h = list(hour_analysis.values)[0]
            hour_str = HourFormatter.format_full(h)
            minute_desc = MinuteFormatter.format(minute_field)
            return f"{freq_str}{hour_str}{minute_desc}执行"

        if min_single and hour_list:
            minute_desc = MinuteFormatter.format(minute_field)
            hour_desc = HourFormatter.format(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        if min_list and hour_list:
            minute_desc = MinuteFormatter.format(minute_field)
            hour_desc = HourFormatter.format(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        if min_step and not hour_step and not hour_wild:
            minute_desc = MinuteFormatter.format(minute_field)
            hour_desc = HourFormatter.format(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        if not min_step and not min_wild and hour_step:
            minute_desc = MinuteFormatter.format(minute_field)
            hour_desc = HourFormatter.format(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        minute_desc = MinuteFormatter.format(minute_field)
        hour_desc = HourFormatter.format(hour_field)
        return f"{freq_str}{hour_desc}{minute_desc}执行"
