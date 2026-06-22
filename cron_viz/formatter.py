from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Set, Optional, Tuple


def parse_field_values(field: str, min_val: int, max_val: int) -> Set[int]:
    values: Set[int] = set()

    for part in field.split(","):
        if part == "?" or part == "*":
            if part == "*":
                values.update(range(min_val, max_val + 1))
            continue
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
        else:
            v = int(part)
            if min_val <= v <= max_val:
                values.add(v)
    return values


@dataclass
class FieldAnalysis:
    raw: str
    type: str
    values: Set[int]
    step: Optional[int] = None
    range_start: Optional[int] = None
    range_end: Optional[int] = None


class BaseFieldFormatter(ABC):
    min_val: int
    max_val: int

    @staticmethod
    def to_ranges(values: List[int]) -> List[Tuple[int, int]]:
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
    def analyze(cls, field: str) -> FieldAnalysis:
        values = parse_field_values(field, cls.min_val, cls.max_val)
        analysis = FieldAnalysis(raw=field, type="UNKNOWN", values=values)

        if field == "*" or field == "?":
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
                analysis.range_end = cls.max_val
                analysis.type = "STEP_FROM"
        elif "-" in field and not field.startswith("-"):
            s, e = field.split("-", 1)
            analysis.range_start = int(s)
            analysis.range_end = int(e)
            analysis.type = "RANGE"
        elif field.isdigit() or (field.startswith("-") and field[1:].isdigit()):
            analysis.type = "SINGLE"

        return analysis

    @classmethod
    def _parse_field_values(cls, field: str) -> Set[int]:
        return parse_field_values(field, cls.min_val, cls.max_val)

    @classmethod
    @abstractmethod
    def format(cls, field: str) -> str:
        ...


class MinuteFormatter(BaseFieldFormatter):
    min_val = 0
    max_val = 59

    @classmethod
    def format(cls, field: str) -> str:
        if field == "*" or field == "?":
            return "每分钟"

        analysis = cls.analyze(field)

        if analysis.type == "SINGLE":
            m = list(analysis.values)[0]
            if m == 0:
                return "整点"
            elif m == 30:
                return "半点"
            else:
                return f"{m}分"

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
            ranges = cls.to_ranges(values)
            range_strs = [f"{s}-{e}分" if s != e else f"{s}分" for s, e in ranges]
            return "、".join(range_strs)

        values = sorted(analysis.values)
        if len(values) == 60:
            return "每分钟"
        if len(values) <= 8:
            return "、".join(f"{v}分" for v in values)
        ranges = cls.to_ranges(values)
        range_strs = [f"{s}-{e}分" if s != e else f"{s}分" for s, e in ranges]
        return "、".join(range_strs)


class HourFormatter(BaseFieldFormatter):
    min_val = 0
    max_val = 23

    @staticmethod
    def format_simple(h: int) -> Tuple[str, int]:
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

    @staticmethod
    def format_full(h: int) -> str:
        period, h12 = HourFormatter.format_simple(h)
        return f"{period}{h12}点"

    @classmethod
    def format(cls, field: str) -> str:
        if field == "*" or field == "?":
            return "每小时"

        analysis = cls.analyze(field)

        if analysis.type == "SINGLE":
            return cls.format_full(list(analysis.values)[0])

        if analysis.type == "STEP_ALL":
            return f"每{analysis.step}小时"

        if analysis.type == "STEP_RANGE":
            s_period, s_h = cls.format_simple(analysis.range_start)
            e_period, e_h = cls.format_simple(analysis.range_end)
            if s_period == e_period:
                return f"{s_period}{s_h}到{e_h}每{analysis.step}小时"
            else:
                return f"{s_period}{s_h}到{e_period}{e_h}每{analysis.step}小时"

        if analysis.type == "STEP_FROM":
            s_period, s_h = cls.format_simple(analysis.range_start)
            return f"从{s_period}{s_h}开始每{analysis.step}小时"

        if analysis.type == "RANGE":
            s = cls.format_full(analysis.range_start)
            e = cls.format_full(analysis.range_end)
            return f"{s}到{e}"

        if analysis.type == "LIST":
            values = sorted(analysis.values)
            if len(values) <= 6:
                return "、".join(cls.format_full(h) for h in values)
            ranges = cls.to_ranges(values)
            range_strs = []
            for s, e in ranges:
                if s == e:
                    range_strs.append(cls.format_full(s))
                else:
                    range_strs.append(f"{cls.format_full(s)}到{cls.format_full(e)}")
            return "、".join(range_strs)

        values = sorted(analysis.values)
        if len(values) == 24:
            return "每小时"
        if len(values) <= 6:
            return "、".join(cls.format_full(h) for h in values)
        ranges = cls.to_ranges(values)
        range_strs = []
        for s, e in ranges:
            if s == e:
                range_strs.append(cls.format_full(s))
            else:
                range_strs.append(f"{cls.format_full(s)}到{cls.format_full(e)}")
        return "、".join(range_strs)


class DayOfMonthFormatter(BaseFieldFormatter):
    min_val = 1
    max_val = 31

    @classmethod
    def format(cls, field: str) -> str:
        if field == "*" or field == "?":
            return ""

        analysis = cls.analyze(field)

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


class MonthFormatter(BaseFieldFormatter):
    min_val = 1
    max_val = 12

    MONTH_NAMES = {
        1: "一月", 2: "二月", 3: "三月", 4: "四月",
        5: "五月", 6: "六月", 7: "七月", 8: "八月",
        9: "九月", 10: "十月", 11: "十一月", 12: "十二月",
    }

    @classmethod
    def _name(cls, m: int) -> str:
        return cls.MONTH_NAMES.get(m, f"{m}月")

    @classmethod
    def format(cls, field: str) -> str:
        if field == "*" or field == "?":
            return ""

        analysis = cls.analyze(field)

        if analysis.type == "SINGLE":
            return cls._name(list(analysis.values)[0])

        if analysis.type == "STEP_ALL":
            return f"每{analysis.step}个月"

        if analysis.type == "STEP_RANGE":
            s = cls._name(analysis.range_start)
            e = cls._name(analysis.range_end)
            return f"{s}到{e}每{analysis.step}个月"

        if analysis.type == "RANGE":
            s = cls._name(analysis.range_start)
            e = cls._name(analysis.range_end)
            return f"{s}到{e}"

        if analysis.type == "LIST":
            values = sorted(analysis.values)
            if len(values) <= 6:
                return "、".join(cls._name(v) for v in values)
            ranges = cls.to_ranges(values)
            range_strs = [
                f"{cls._name(s)}到{cls._name(e)}" if s != e else cls._name(s)
                for s, e in ranges
            ]
            return "、".join(range_strs)

        values = sorted(analysis.values)
        if len(values) == 12:
            return ""
        if len(values) <= 6:
            return "、".join(cls._name(v) for v in values)
        return ""


class DayOfWeekFormatter(BaseFieldFormatter):
    min_val = 0
    max_val = 7

    WEEKDAY_NAMES = {
        0: "周日", 1: "周一", 2: "周二", 3: "周三",
        4: "周四", 5: "周五", 6: "周六", 7: "周日",
    }

    @classmethod
    def _name(cls, d: int) -> str:
        return cls.WEEKDAY_NAMES.get(d, f"周{d}")

    @classmethod
    def _normalize(cls, values: Set[int]) -> List[int]:
        normalized = set()
        for v in values:
            normalized.add(0 if v == 7 else v)
        return sorted(normalized)

    @classmethod
    def format(cls, field: str) -> str:
        if field == "*" or field == "?":
            return ""

        analysis = cls.analyze(field)
        values = cls._normalize(analysis.values)

        if len(values) == 0:
            return ""
        if len(values) == 1:
            return cls._name(values[0])
        if len(values) == 7:
            return "每天"
        if set(values) == {1, 2, 3, 4, 5}:
            return "工作日"
        if set(values) == {0, 6}:
            return "周末"

        if analysis.type == "STEP_ALL":
            return f"每{analysis.step}天"

        if analysis.type == "RANGE":
            s = cls._name(analysis.range_start)
            e = cls._name(0 if analysis.range_end == 7 else analysis.range_end)
            return f"{s}到{e}"

        if analysis.type == "LIST" or len(values) <= 5:
            return "、".join(cls._name(v) for v in values)

        ranges = cls.to_ranges(values)
        range_strs = [
            f"{cls._name(s)}到{cls._name(e)}" if s != e else cls._name(s)
            for s, e in ranges
        ]
        return "、".join(range_strs)
