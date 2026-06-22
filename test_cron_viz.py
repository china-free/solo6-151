import unittest
from datetime import datetime
from cron_viz.parser import CronParser, CronExpression
from cron_viz.scheduler import CronScheduler
from cron_viz.conflict_detector import ConflictDetector


class TestCronParser(unittest.TestCase):
    def test_parse_basic_expression(self):
        expr = CronParser.parse("30 14 * * 3", "测试任务")
        self.assertEqual(expr.minute, "30")
        self.assertEqual(expr.hour, "14")
        self.assertEqual(expr.day_of_month, "*")
        self.assertEqual(expr.month, "*")
        self.assertEqual(expr.day_of_week, "3")
        self.assertEqual(expr.name, "测试任务")

    def test_parse_invalid_expression(self):
        with self.assertRaises(ValueError):
            CronParser.parse("30 14 * *")

    def test_human_readable_wednesday_2pm(self):
        expr = CronParser.parse("30 14 * * 3")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("周三", desc)
        self.assertIn("下午", desc)
        self.assertIn("2", desc)
        self.assertIn("半", desc)

    def test_human_readable_every_15_minutes(self):
        expr = CronParser.parse("*/15 * * * *")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("每15分钟", desc)

    def test_human_readable_workday_morning(self):
        expr = CronParser.parse("0 8 * * 1-5")
        desc = CronParser.to_human_readable(expr)
        self.assertTrue("工作日" in desc or "周一" in desc)
        self.assertIn("上午8点", desc)
        self.assertIn("整", desc)

    def test_human_readable_step_with_range(self):
        expr = CronParser.parse("10-30/5 * * * *")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("10-30分", desc)
        self.assertIn("每5分钟", desc)

    def test_human_readable_list_minutes(self):
        expr = CronParser.parse("1,3,5 * * * *")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("1分", desc)
        self.assertIn("3分", desc)
        self.assertIn("5分", desc)

    def test_human_readable_step_hours(self):
        expr = CronParser.parse("0 */6 * * *")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("每6小时", desc)
        self.assertIn("整点", desc)

    def test_human_readable_step_range_hours(self):
        expr = CronParser.parse("0 8-18/2 * * *")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("上午8", desc)
        self.assertIn("下午6", desc)
        self.assertIn("每2小时", desc)

    def test_human_readable_list_hours(self):
        expr = CronParser.parse("0 1,3,5 * * *")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("凌晨1点", desc)
        self.assertIn("凌晨3点", desc)
        self.assertIn("凌晨5点", desc)

    def test_human_readable_list_dow(self):
        expr = CronParser.parse("0 8 * * 1,3,5")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("周一", desc)
        self.assertIn("周三", desc)
        self.assertIn("周五", desc)

    def test_human_readable_complex_combined(self):
        expr = CronParser.parse("*/5 */2 * * *")
        desc = CronParser.to_human_readable(expr)
        self.assertIn("每2小时", desc)
        self.assertIn("每5分钟", desc)

    def test_describe_minute_step_all(self):
        self.assertEqual(CronParser.describe_minute("*/15"), "每15分钟")
        self.assertEqual(CronParser.describe_minute("*/5"), "每5分钟")

    def test_describe_minute_step_range(self):
        self.assertEqual(CronParser.describe_minute("10-30/5"), "10-30分每5分钟")
        self.assertEqual(CronParser.describe_minute("0-10/2"), "0-10分每2分钟")

    def test_describe_minute_list(self):
        self.assertEqual(CronParser.describe_minute("0,30"), "整点和半点")
        self.assertEqual(CronParser.describe_minute("1,3,5"), "1分、3分、5分")
        self.assertEqual(CronParser.describe_minute("0,15,30,45"), "每刻钟")

    def test_describe_hour_step_all(self):
        self.assertEqual(CronParser.describe_hour("*/2"), "每2小时")
        self.assertEqual(CronParser.describe_hour("*/6"), "每6小时")

    def test_describe_hour_step_range(self):
        result = CronParser.describe_hour("8-18/2")
        self.assertIn("上午8", result)
        self.assertIn("下午6", result)
        self.assertIn("每2小时", result)

    def test_describe_hour_list(self):
        result = CronParser.describe_hour("1,3,5")
        self.assertIn("凌晨1点", result)
        self.assertIn("凌晨3点", result)
        self.assertIn("凌晨5点", result)

    def test_parse_field_values(self):
        values = CronParser._parse_field_values("*/15", 0, 59)
        self.assertEqual(values, {0, 15, 30, 45})

        values = CronParser._parse_field_values("1-5", 0, 7)
        self.assertEqual(values, {1, 2, 3, 4, 5})

        values = CronParser._parse_field_values("0,30", 0, 59)
        self.assertEqual(values, {0, 30})


class TestCronScheduler(unittest.TestCase):
    def test_calculate_executions_hourly(self):
        expr = CronParser.parse("0 * * * *", "整点任务")
        start = datetime(2025, 6, 22, 0, 0, 0)
        end = datetime(2025, 6, 22, 5, 0, 0)
        result = CronScheduler.calculate_executions(expr, start, end)
        self.assertEqual(len(result.executions), 5)
        self.assertEqual(result.executions[0].time.hour, 0)
        self.assertEqual(result.executions[-1].time.hour, 4)

    def test_calculate_executions_weekly(self):
        expr = CronParser.parse("0 9 * * 3", "每周三9点")
        start = datetime(2025, 6, 16, 0, 0, 0)
        end = datetime(2025, 6, 30, 0, 0, 0)
        result = CronScheduler.calculate_executions(expr, start, end)
        self.assertGreaterEqual(len(result.executions), 2)

    def test_calculate_multiple(self):
        exprs = [
            CronParser.parse("0 * * * *", "task1"),
            CronParser.parse("30 * * * *", "task2"),
        ]
        start = datetime(2025, 6, 22, 0, 0, 0)
        end = datetime(2025, 6, 22, 3, 0, 0)
        results = CronScheduler.calculate_multiple(exprs, start, end)
        self.assertEqual(len(results), 2)
        self.assertEqual(results["task1"].count, 3)
        self.assertEqual(results["task2"].count, 3)


class TestConflictDetector(unittest.TestCase):
    def test_detect_conflicts(self):
        start = datetime(2025, 6, 22, 0, 0, 0)
        end = datetime(2025, 6, 22, 2, 0, 0)

        exprs = [
            CronParser.parse("0 * * * *", "task1"),
            CronParser.parse("0 * * * *", "task2"),
            CronParser.parse("30 * * * *", "task3"),
        ]
        results = CronScheduler.calculate_multiple(exprs, start, end)
        conflicts = ConflictDetector.detect(results)

        self.assertGreaterEqual(len(conflicts), 2)
        for c in conflicts:
            self.assertIn("task1", c.tasks)
            self.assertIn("task2", c.tasks)

    def test_no_conflicts(self):
        start = datetime(2025, 6, 22, 0, 0, 0)
        end = datetime(2025, 6, 22, 2, 0, 0)

        exprs = [
            CronParser.parse("0 * * * *", "task1"),
            CronParser.parse("15 * * * *", "task2"),
        ]
        results = CronScheduler.calculate_multiple(exprs, start, end)
        conflicts = ConflictDetector.detect(results)

        self.assertEqual(len(conflicts), 0)

    def test_summarize(self):
        start = datetime(2025, 6, 22, 0, 0, 0)
        end = datetime(2025, 6, 22, 3, 0, 0)

        exprs = [
            CronParser.parse("0 * * * *", "task1"),
            CronParser.parse("0 * * * *", "task2"),
            CronParser.parse("0 * * * *", "task3"),
        ]
        results = CronScheduler.calculate_multiple(exprs, start, end)
        conflicts = ConflictDetector.detect(results)
        summary = ConflictDetector.summarize(conflicts)

        self.assertEqual(summary["total_conflicts"], 3)
        self.assertEqual(summary["max_tasks_at_once"], 3)
        self.assertEqual(summary["unique_conflicting_tasks"], 3)


if __name__ == "__main__":
    unittest.main()
