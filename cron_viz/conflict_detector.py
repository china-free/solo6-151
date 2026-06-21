from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Set
from collections import defaultdict

from .scheduler import ExecutionPoint, ScheduleResult


@dataclass
class Conflict:
    time: datetime
    minute_key: str
    tasks: List[str] = field(default_factory=list)

    @property
    def severity(self) -> str:
        n = len(self.tasks)
        if n >= 10:
            return "CRITICAL"
        elif n >= 5:
            return "HIGH"
        elif n >= 3:
            return "MEDIUM"
        else:
            return "LOW"

    @property
    def count(self) -> int:
        return len(self.tasks)


class ConflictDetector:
    def __init__(self):
        pass

    @staticmethod
    def detect(schedule_results: Dict[str, ScheduleResult]) -> List[Conflict]:
        minute_groups: Dict[str, List[ExecutionPoint]] = defaultdict(list)

        for key, result in schedule_results.items():
            for exec_point in result.executions:
                minute_groups[exec_point.minute_key].append(exec_point)

        conflicts: List[Conflict] = []
        for minute_key, executions in sorted(minute_groups.items()):
            if len(executions) >= 2:
                task_names = list(set(
                    e.cron_expr.name if e.cron_expr.name else str(e.cron_expr)
                    for e in executions
                ))
                if len(task_names) >= 2:
                    conflict = Conflict(
                        time=executions[0].time,
                        minute_key=minute_key,
                        tasks=task_names,
                    )
                    conflicts.append(conflict)

        conflicts.sort(key=lambda c: c.time)
        return conflicts

    @staticmethod
    def get_conflict_minutes(conflicts: List[Conflict]) -> Set[str]:
        return {c.minute_key for c in conflicts}

    @staticmethod
    def summarize(conflicts: List[Conflict]) -> Dict:
        summary = {
            "total_conflicts": len(conflicts),
            "by_severity": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "max_tasks_at_once": 0,
            "total_conflicting_tasks": 0,
            "all_conflicting_tasks": set(),
        }

        for c in conflicts:
            summary["by_severity"][c.severity] += 1
            if c.count > summary["max_tasks_at_once"]:
                summary["max_tasks_at_once"] = c.count
            summary["total_conflicting_tasks"] += c.count
            for t in c.tasks:
                summary["all_conflicting_tasks"].add(t)

        summary["all_conflicting_tasks"] = sorted(summary["all_conflicting_tasks"])
        summary["unique_conflicting_tasks"] = len(summary["all_conflicting_tasks"])

        return summary
