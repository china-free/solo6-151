from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from croniter import croniter

from .parser import CronExpression


@dataclass
class ExecutionPoint:
    time: datetime
    cron_expr: CronExpression
    minute_key: str = field(init=False)

    def __post_init__(self):
        self.minute_key = self.time.strftime("%Y-%m-%d %H:%M")

    def __lt__(self, other):
        if not isinstance(other, ExecutionPoint):
            return NotImplemented
        return self.time < other.time

    def __repr__(self):
        return f"ExecutionPoint(time={self.time.isoformat()}, name={self.cron_expr.name})"


@dataclass
class ScheduleResult:
    cron_expr: CronExpression
    executions: List[ExecutionPoint] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.executions)


class CronScheduler:
    def __init__(self):
        pass

    @staticmethod
    def calculate_executions(
        expr: CronExpression,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        days: Optional[int] = None,
        max_executions: int = 10000,
    ) -> ScheduleResult:
        if start_time is None:
            start_time = datetime.now().replace(second=0, microsecond=0)
        else:
            start_time = start_time.replace(second=0, microsecond=0)

        if end_time is None and days is not None:
            end_time = start_time + timedelta(days=days)
        elif end_time is None:
            end_time = start_time + timedelta(days=7)
        else:
            end_time = end_time.replace(second=0, microsecond=0)

        result = ScheduleResult(cron_expr=expr)
        cron_str = str(expr)

        try:
            iter = croniter(cron_str, start_time)
        except Exception as e:
            raise ValueError(f"Invalid cron expression '{cron_str}': {e}")

        count = 0

        if start_time <= end_time:
            try:
                prev_time = iter.get_prev(datetime)
                if prev_time == start_time:
                    result.executions.append(
                        ExecutionPoint(time=start_time, cron_expr=expr)
                    )
                    count += 1
            except (StopIteration, Exception):
                pass

        while count < max_executions:
            try:
                next_time = iter.get_next(datetime)
            except (StopIteration, Exception):
                break

            if next_time >= end_time:
                break

            next_time = next_time.replace(second=0, microsecond=0)
            result.executions.append(ExecutionPoint(time=next_time, cron_expr=expr))
            count += 1

        return result

    @staticmethod
    def calculate_multiple(
        expressions: List[CronExpression],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        days: Optional[int] = None,
    ) -> Dict[str, ScheduleResult]:
        results: Dict[str, ScheduleResult] = {}
        for expr in expressions:
            key = expr.name if expr.name else str(expr)
            results[key] = CronScheduler.calculate_executions(
                expr, start_time, end_time, days
            )
        return results

    @staticmethod
    def get_all_executions_sorted(
        results: Dict[str, ScheduleResult]
    ) -> List[ExecutionPoint]:
        all_execs = []
        for result in results.values():
            all_execs.extend(result.executions)
        all_execs.sort()
        return all_execs
