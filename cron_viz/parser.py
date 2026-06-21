import re
from dataclasses import dataclass, field
from typing import List, Set, Optional


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
    MONTHS = {
        1: "一月", 2: "二月", 3: "三月", 4: "四月",
        5: "五月", 6: "六月", 7: "七月", 8: "八月",
        9: "九月", 10: "十月", 11: "十一月", 12: "十二月",
    }

    WEEKDAYS = {
        0: "周日", 1: "周一", 2: "周二", 3: "周三",
        4: "周四", 5: "周五", 6: "周六", 7: "周日",
    }

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

    @classmethod
    def _parse_field_values(cls, field: str, min_val: int, max_val: int) -> Set[int]:
        values: Set[int] = set()

        for part in field.split(","):
            if "/" in part:
                base, step_str = part.split("/", 1)
                step = int(step_str)
                if base == "*":
                    start, end = min_val, max_val
                elif "-" in base:
                    s, e = base.split("-", 1)
                    start, end = int(s), int(e)
                else:
                    start, end = int(base), max_val
                for v in range(start, end + 1, step):
                    if min_val <= v <= max_val:
                        values.add(v)
            elif "-" in part and not part.startswith("-"):
                start, end = part.split("-", 1)
                for v in range(int(start), int(end) + 1):
                    if min_val <= v <= max_val:
                        values.add(v)
            elif part == "*":
                values.update(range(min_val, max_val + 1))
            else:
                v = int(part)
                if min_val <= v <= max_val:
                    values.add(v)

        return values

    @classmethod
    def describe_minute(cls, minute_field: str) -> str:
        if minute_field == "*":
            return "每分钟"
        values = sorted(cls._parse_field_values(minute_field, 0, 59))
        if len(values) == 0:
            return ""
        if len(values) == 1:
            return f"第 {values[0]} 分"
        if len(values) == 60:
            return "每分钟"

        has_step = bool(re.search(r"/\d+", minute_field))
        if has_step:
            step_match = re.search(r"/(\d+)", minute_field)
            if step_match:
                step = int(step_match.group(1))
                return f"每 {step} 分钟"

        if len(values) <= 8:
            return f"在 {', '.join(str(v) for v in values)} 分"
        ranges = cls._to_ranges(values)
        parts = []
        for s, e in ranges:
            if s == e:
                parts.append(f"{s} 分")
            else:
                parts.append(f"{s}-{e} 分")
        return "在 " + ", ".join(parts)

    @classmethod
    def describe_hour(cls, hour_field: str) -> str:
        if hour_field == "*":
            return "每小时"
        values = sorted(cls._parse_field_values(hour_field, 0, 23))
        if len(values) == 0:
            return ""
        if len(values) == 1:
            h = values[0]
            period = "上午" if h < 12 else "下午"
            h12 = h if h <= 12 else h - 12
            if h12 == 0:
                h12 = 12
            return f"{period} {h12} 点"
        if len(values) == 24:
            return "每小时"

        has_step = bool(re.search(r"/\d+", hour_field))
        if has_step:
            step_match = re.search(r"/(\d+)", hour_field)
            if step_match:
                step = int(step_match.group(1))
                return f"每 {step} 小时"

        if len(values) <= 6:
            formatted = []
            for h in values:
                period = "上午" if h < 12 else "下午"
                h12 = h if h <= 12 else h - 12
                if h12 == 0:
                    h12 = 12
                formatted.append(f"{period}{h12}点")
            return "在 " + ", ".join(formatted)
        ranges = cls._to_ranges(values)
        parts = []
        for s, e in ranges:
            if s == e:
                period = "上午" if s < 12 else "下午"
                h12 = s if s <= 12 else s - 12
                if h12 == 0:
                    h12 = 12
                parts.append(f"{period}{h12}点")
            else:
                parts.append(f"{s}-{e} 点")
        return "在 " + ", ".join(parts)

    @classmethod
    def describe_day_of_month(cls, dom_field: str) -> str:
        if dom_field == "*":
            return ""
        if dom_field == "?":
            return ""
        values = sorted(cls._parse_field_values(dom_field, 1, 31))
        if len(values) == 0:
            return ""
        if len(values) == 1:
            return f"每月 {values[0]} 号"
        if len(values) == 31:
            return "每天"

        has_step = bool(re.search(r"/\d+", dom_field))
        if has_step:
            step_match = re.search(r"/(\d+)", dom_field)
            if step_match:
                step = int(step_match.group(1))
                return f"每 {step} 天"

        if len(values) <= 10:
            return f"在 {', '.join(str(v) + '号' for v in values)}"
        return "在特定日期"

    @classmethod
    def describe_month(cls, month_field: str) -> str:
        if month_field == "*":
            return ""
        values = sorted(cls._parse_field_values(month_field, 1, 12))
        if len(values) == 0:
            return ""
        if len(values) == 1:
            return cls.MONTHS.get(values[0], f"{values[0]} 月")
        if len(values) == 12:
            return ""

        if len(values) <= 6:
            return "在 " + ", ".join(cls.MONTHS.get(v, f"{v}月") for v in values)
        ranges = cls._to_ranges(values)
        parts = []
        for s, e in ranges:
            if s == e:
                parts.append(cls.MONTHS.get(s, f"{s}月"))
            else:
                parts.append(f"{cls.MONTHS.get(s, f'{s}月')}到{cls.MONTHS.get(e, f'{e}月')}")
        return "在 " + ", ".join(parts)

    @classmethod
    def describe_day_of_week(cls, dow_field: str) -> str:
        if dow_field == "*":
            return ""
        if dow_field == "?":
            return ""
        values = sorted(cls._parse_field_values(dow_field, 0, 7))
        normalized = set()
        for v in values:
            normalized.add(0 if v == 7 else v)
        values = sorted(normalized)

        if len(values) == 0:
            return ""
        if len(values) == 1:
            return cls.WEEKDAYS.get(values[0], f"周{values[0]}")
        if len(values) == 7:
            return "每天"

        if set(values) == {1, 2, 3, 4, 5}:
            return "工作日"
        if set(values) == {0, 6}:
            return "周末"

        if len(values) <= 5:
            return "每" + ", ".join(cls.WEEKDAYS.get(v, f"周{v}") for v in values)

        ranges = cls._to_ranges(values)
        parts = []
        for s, e in ranges:
            if s == e:
                parts.append(cls.WEEKDAYS.get(s, f"周{s}"))
            else:
                parts.append(f"{cls.WEEKDAYS.get(s, f'周{s}')}到{cls.WEEKDAYS.get(e, f'周{e}')}")
        return "每" + ", ".join(parts)

    @staticmethod
    def _to_ranges(values: List[int]) -> List[tuple]:
        if not values:
            return []
        ranges = []
        start = values[0]
        prev = values[0]
        for v in values[1:]:
            if v == prev + 1:
                prev = v
            else:
                ranges.append((start, prev))
                start = v
                prev = v
        ranges.append((start, prev))
        return ranges

    @classmethod
    def to_human_readable(cls, expr: CronExpression) -> str:
        parts = []

        dom_desc = cls.describe_day_of_month(expr.day_of_month)
        dow_desc = cls.describe_day_of_week(expr.day_of_week)
        month_desc = cls.describe_month(expr.month)
        hour_desc = cls.describe_hour(expr.hour)
        minute_desc = cls.describe_minute(expr.minute)

        if month_desc:
            parts.append(month_desc)

        if dom_desc and dow_desc:
            parts.append(f"{dom_desc} 以及 {dow_desc}")
        elif dom_desc:
            parts.append(dom_desc)
        elif dow_desc:
            parts.append(dow_desc)
        else:
            parts.append("每天")

        if hour_desc and not hour_desc.startswith("每"):
            parts.append(hour_desc)
        elif hour_desc:
            parts.append(hour_desc)

        if minute_desc and not minute_desc.startswith("每"):
            parts.append(minute_desc)
        elif minute_desc:
            parts.append(minute_desc)

        result = " ".join(p for p in parts if p)

        if expr.minute == "*" and expr.hour == "*":
            pass
        elif expr.minute != "*" and expr.hour != "*":
            if not (minute_desc.startswith("每") or hour_desc.startswith("每")):
                hour_vals = sorted(cls._parse_field_values(expr.hour, 0, 23))
                minute_vals = sorted(cls._parse_field_values(expr.minute, 0, 59))
                if len(hour_vals) == 1 and len(minute_vals) == 1:
                    h = hour_vals[0]
                    m = minute_vals[0]
                    period = "上午" if h < 12 else "下午"
                    h12 = h if h <= 12 else h - 12
                    if h12 == 0:
                        h12 = 12
                    time_part = f"{period} {h12} 点 {m:02d} 分"
                    freq_parts = []
                    if month_desc:
                        freq_parts.append(month_desc)
                    if dom_desc and dow_desc:
                        freq_parts.append(f"{dom_desc} 以及 {dow_desc}")
                    elif dom_desc:
                        freq_parts.append(dom_desc)
                    elif dow_desc:
                        freq_parts.append(dow_desc)
                    else:
                        freq_parts.append("每天")
                    result = " ".join(p for p in freq_parts if p) + " " + time_part + " 执行"
                    return result.strip()

        return result.strip() + " 执行"
