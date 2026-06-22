import re
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Tuple


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


@dataclass
class FieldAnalysis:
    raw: str
    type: str
    values: Set[int]
    step: Optional[int] = None
    range_start: Optional[int] = None
    range_end: Optional[int] = None


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
    def _analyze_field(cls, field: str, min_val: int, max_val: int) -> FieldAnalysis:
        values = cls._parse_field_values(field, min_val, max_val)
        analysis = FieldAnalysis(raw=field, type="UNKNOWN", values=values)

        if field == "*":
            analysis.type = "WILDCARD"
        elif "," in field and "/" not in field and "-" not in field:
            analysis.type = "LIST"
        elif "/" in field:
            base, step_str = field.split("/", 1)
            analysis.step = int(step_str)
            if base == "*":
                analysis.type = "STEP_ALL"
            elif "-" in base:
                s, e = base.split("-", 1)
                analysis.range_start = int(s)
                analysis.range_end = int(e)
                analysis.type = "STEP_RANGE"
            else:
                analysis.range_start = int(base)
                analysis.range_end = max_val
                analysis.type = "STEP_FROM"
        elif "-" in field:
            s, e = field.split("-", 1)
            analysis.range_start = int(s)
            analysis.range_end = int(e)
            analysis.type = "RANGE"
        elif field.isdigit() or (field.startswith("-") and field[1:].isdigit()):
            analysis.type = "SINGLE"

        return analysis

    @staticmethod
    def _format_hour(h: int) -> str:
        if h == 0:
            return "凌晨0点"
        elif h < 6:
            return f"凌晨{h}点"
        elif h < 12:
            return f"上午{h}点"
        elif h == 12:
            return "中午12点"
        elif h < 19:
            return f"下午{h-12}点"
        else:
            return f"晚上{h-12}点"

    @staticmethod
    def _format_hour_simple(h: int) -> Tuple[str, int]:
        if h == 0:
            return "凌晨", 0
        elif h < 6:
            return "凌晨", h
        elif h < 12:
            return "上午", h
        elif h == 12:
            return "中午", 12
        elif h < 19:
            return "下午", h - 12
        else:
            return "晚上", h - 12

    @classmethod
    def describe_minute(cls, minute_field: str) -> str:
        analysis = cls._analyze_field(minute_field, 0, 59)

        if analysis.type == "WILDCARD":
            return "每分钟"

        if analysis.type == "SINGLE":
            m = list(analysis.values)[0]
            if m == 0:
                return "整点"
            elif m == 30:
                return "半点"
            else:
                return f"{m:02d}分"

        if analysis.type == "STEP_ALL":
            return f"每{analysis.step}分钟"

        if analysis.type == "STEP_RANGE":
            return f"{analysis.range_start}-{analysis.range_end}分每{analysis.step}分钟"

        if analysis.type == "STEP_FROM":
            return f"从{analysis.range_start}分开始每{analysis.step}分钟"

        if analysis.type == "RANGE":
            return f"{analysis.range_start}-{analysis.range_end}分"

        if analysis.type == "LIST":
            values = sorted(analysis.values)
            if len(values) == 2 and 0 in values and 30 in values:
                return "整点和半点"
            if set(values) == set(range(0, 60, 15)):
                return "每刻钟"
            formatted = []
            for v in values:
                if v == 0:
                    formatted.append("整点")
                elif v == 30:
                    formatted.append("半点")
                else:
                    formatted.append(f"{v}分")
            if len(formatted) <= 6:
                return "、".join(formatted)
            ranges = cls._to_ranges(values)
            range_strs = []
            for s, e in ranges:
                if s == e:
                    range_strs.append(f"{s}分")
                else:
                    range_strs.append(f"{s}-{e}分")
            return "、".join(range_strs)

        values = sorted(analysis.values)
        if len(values) == 60:
            return "每分钟"
        if len(values) <= 8:
            return "、".join(f"{v}分" for v in values)
        ranges = cls._to_ranges(values)
        range_strs = []
        for s, e in ranges:
            if s == e:
                range_strs.append(f"{s}分")
            else:
                range_strs.append(f"{s}-{e}分")
        return "、".join(range_strs)

    @classmethod
    def describe_hour(cls, hour_field: str) -> str:
        analysis = cls._analyze_field(hour_field, 0, 23)

        if analysis.type == "WILDCARD":
            return "每小时"

        if analysis.type == "SINGLE":
            h = list(analysis.values)[0]
            return cls._format_hour(h)

        if analysis.type == "STEP_ALL":
            return f"每{analysis.step}小时"

        if analysis.type == "STEP_RANGE":
            s_period, s_h = cls._format_hour_simple(analysis.range_start)
            e_period, e_h = cls._format_hour_simple(analysis.range_end)
            if s_period == e_period:
                return f"{s_period}{s_h}到{e_h}每{analysis.step}小时"
            else:
                return f"{s_period}{s_h}到{e_period}{e_h}每{analysis.step}小时"

        if analysis.type == "STEP_FROM":
            s_period, s_h = cls._format_hour_simple(analysis.range_start)
            return f"从{s_period}{s_h}开始每{analysis.step}小时"

        if analysis.type == "RANGE":
            s = cls._format_hour(analysis.range_start)
            e = cls._format_hour(analysis.range_end)
            return f"{s}到{e}"

        if analysis.type == "LIST":
            values = sorted(analysis.values)
            if len(values) <= 6:
                return "、".join(cls._format_hour(h) for h in values)
            ranges = cls._to_ranges(values)
            range_strs = []
            for s, e in ranges:
                if s == e:
                    range_strs.append(cls._format_hour(s))
                else:
                    range_strs.append(f"{cls._format_hour(s)}到{cls._format_hour(e)}")
            return "、".join(range_strs)

        values = sorted(analysis.values)
        if len(values) == 24:
            return "每小时"
        if len(values) <= 6:
            return "、".join(cls._format_hour(h) for h in values)
        ranges = cls._to_ranges(values)
        range_strs = []
        for s, e in ranges:
            if s == e:
                range_strs.append(cls._format_hour(s))
            else:
                range_strs.append(f"{cls._format_hour(s)}到{cls._format_hour(e)}")
        return "、".join(range_strs)

    @classmethod
    def describe_day_of_month(cls, dom_field: str) -> str:
        if dom_field == "*" or dom_field == "?":
            return ""

        analysis = cls._analyze_field(dom_field, 1, 31)

        if analysis.type == "SINGLE":
            return f"每月{list(analysis.values)[0]}号"

        if analysis.type == "STEP_ALL":
            return f"每{analysis.step}天"

        if analysis.type == "STEP_RANGE":
            return f"{analysis.range_start}-{analysis.range_end}号每{analysis.step}天"

        if analysis.type == "STEP_FROM":
            return f"从{analysis.range_start}号开始每{analysis.step}天"

        if analysis.type == "RANGE":
            return f"{analysis.range_start}-{analysis.range_end}号"

        if analysis.type == "LIST":
            values = sorted(analysis.values)
            if len(values) <= 10:
                return "、".join(f"{v}号" for v in values)
            return "特定日期"

        values = sorted(analysis.values)
        if len(values) == 31:
            return "每天"
        if len(values) <= 10:
            return "、".join(f"{v}号" for v in values)
        return "特定日期"

    @classmethod
    def describe_month(cls, month_field: str) -> str:
        if month_field == "*":
            return ""

        analysis = cls._analyze_field(month_field, 1, 12)

        if analysis.type == "SINGLE":
            return cls.MONTHS.get(list(analysis.values)[0], f"{list(analysis.values)[0]}月")

        if analysis.type == "STEP_ALL":
            return f"每{analysis.step}个月"

        if analysis.type == "STEP_RANGE":
            s = cls.MONTHS.get(analysis.range_start, f"{analysis.range_start}月")
            e = cls.MONTHS.get(analysis.range_end, f"{analysis.range_end}月")
            return f"{s}到{e}每{analysis.step}个月"

        if analysis.type == "RANGE":
            s = cls.MONTHS.get(analysis.range_start, f"{analysis.range_start}月")
            e = cls.MONTHS.get(analysis.range_end, f"{analysis.range_end}月")
            return f"{s}到{e}"

        if analysis.type == "LIST":
            values = sorted(analysis.values)
            if len(values) <= 6:
                return "、".join(cls.MONTHS.get(v, f"{v}月") for v in values)
            ranges = cls._to_ranges(values)
            range_strs = []
            for s, e in ranges:
                if s == e:
                    range_strs.append(cls.MONTHS.get(s, f"{s}月"))
                else:
                    range_strs.append(
                        f"{cls.MONTHS.get(s, f'{s}月')}到{cls.MONTHS.get(e, f'{e}月')}"
                    )
            return "、".join(range_strs)

        values = sorted(analysis.values)
        if len(values) == 12:
            return ""
        if len(values) <= 6:
            return "、".join(cls.MONTHS.get(v, f"{v}月") for v in values)
        return ""

    @classmethod
    def describe_day_of_week(cls, dow_field: str) -> str:
        if dow_field == "*" or dow_field == "?":
            return ""

        analysis = cls._analyze_field(dow_field, 0, 7)
        normalized = set()
        for v in analysis.values:
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

        if analysis.type == "STEP_ALL":
            return f"每{analysis.step}天"

        if analysis.type == "RANGE":
            s = cls.WEEKDAYS.get(analysis.range_start, f"周{analysis.range_start}")
            e = cls.WEEKDAYS.get(
                0 if analysis.range_end == 7 else analysis.range_end,
                f"周{analysis.range_end}"
            )
            return f"{s}到{e}"

        if analysis.type == "LIST" or len(values) <= 5:
            return "、".join(cls.WEEKDAYS.get(v, f"周{v}") for v in values)

        ranges = cls._to_ranges(values)
        range_strs = []
        for s, e in ranges:
            if s == e:
                range_strs.append(cls.WEEKDAYS.get(s, f"周{s}"))
            else:
                range_strs.append(f"{cls.WEEKDAYS.get(s, f'周{s}')}到{cls.WEEKDAYS.get(e, f'周{e}')}")
        return "、".join(range_strs)

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
        minute_field = expr.minute
        hour_field = expr.hour
        dom_field = expr.day_of_month
        month_field = expr.month
        dow_field = expr.day_of_week

        minute_analysis = cls._analyze_field(minute_field, 0, 59)
        hour_analysis = cls._analyze_field(hour_field, 0, 23)

        dom_desc = cls.describe_day_of_month(dom_field)
        dow_desc = cls.describe_day_of_week(dow_field)
        month_desc = cls.describe_month(month_field)

        freq_parts = []
        if month_desc:
            freq_parts.append(month_desc)

        if dom_desc and dow_desc:
            freq_parts.append(f"{dom_desc}以及{dow_desc}")
        elif dom_desc:
            freq_parts.append(dom_desc)
        elif dow_desc:
            freq_parts.append(dow_desc)

        if not any(freq_parts):
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
            minute_desc = cls.describe_minute(minute_field)
            return f"{freq_str}{minute_desc}执行"

        if min_wild and hour_step:
            hour_desc = cls.describe_hour(hour_field)
            return f"{freq_str}{hour_desc}每分钟执行"

        if min_step and hour_step:
            minute_desc = cls.describe_minute(minute_field)
            hour_desc = cls.describe_hour(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        if min_single and hour_single:
            m = list(minute_analysis.values)[0]
            h = list(hour_analysis.values)[0]
            period, h12 = cls._format_hour_simple(h)
            if m == 0:
                time_str = f"{period}{h12}点整"
            elif m == 30:
                time_str = f"{period}{h12}点半"
            else:
                time_str = f"{period}{h12}点{m:02d}分"
            return f"{freq_str}{time_str}执行"

        if min_list and hour_single:
            h = list(hour_analysis.values)[0]
            hour_str = cls._format_hour(h)
            minute_desc = cls.describe_minute(minute_field)
            return f"{freq_str}{hour_str}{minute_desc}执行"

        if min_single and hour_list:
            minute_desc = cls.describe_minute(minute_field)
            hour_desc = cls.describe_hour(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        if min_list and hour_list:
            minute_desc = cls.describe_minute(minute_field)
            hour_desc = cls.describe_hour(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        if min_step and not hour_step and not hour_wild:
            minute_desc = cls.describe_minute(minute_field)
            hour_desc = cls.describe_hour(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        if not min_step and not min_wild and hour_step:
            minute_desc = cls.describe_minute(minute_field)
            hour_desc = cls.describe_hour(hour_field)
            return f"{freq_str}{hour_desc}{minute_desc}执行"

        minute_desc = cls.describe_minute(minute_field)
        hour_desc = cls.describe_hour(hour_field)
        return f"{freq_str}{hour_desc}{minute_desc}执行"
