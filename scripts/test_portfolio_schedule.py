from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import unittest
from zoneinfo import ZoneInfo

from portfolio_schedule import WEEKLY_CRONS, plan


class ScheduleTests(unittest.TestCase):
    def test_dst_and_standard_time(self):
        for day, active in [('2026-07-10', '14'), ('2026-11-06', '15'),
                            ('2026-12-11', '15')]:
            for hour in ['14', '15']:
                with self.subTest(day=day, hour=hour):
                    # A late runner still selects the intended cron hour.
                    result = plan('schedule', f'0 {hour} * * 5', now=
                                  datetime.fromisoformat(day + 'T16:30:00+00:00'))
                    self.assertEqual(result, (hour == active, hour == active))

    def test_exactly_one_friday_refresh_across_dst_transitions(self):
        day = datetime(2026, 1, 1, 17, tzinfo=timezone.utc)
        while day.year <= 2027:
            if day.weekday() == 4:
                selected = [cron for cron in WEEKLY_CRONS
                            if plan('schedule', cron, now=day) == (True, True)]
                with self.subTest(day=day.date()):
                    self.assertEqual(len(selected), 1)
                    intended = day.replace(hour=int(selected[0].split()[1]), minute=0)
                    local = intended.astimezone(ZoneInfo('America/New_York'))
                    self.assertEqual((local.weekday(), local.hour), (4, 10))
            day += timedelta(days=1)

    def test_non_friday_weekly_candidates_are_skipped(self):
        for day in ['2026-11-05', '2026-11-07']:
            for cron in WEEKLY_CRONS:
                with self.subTest(day=day, cron=cron):
                    self.assertEqual(plan('schedule', cron, now=
                                     datetime.fromisoformat(day + 'T16:30:00+00:00')),
                                     (False, False))

    def test_preserves_daily_and_manual(self):
        for cron in ['0 13 * * *', '0 22 * * *']:
            self.assertEqual(plan('schedule', cron), (True, False))
            self.assertEqual(plan('schedule', cron, requested=True), (True, False))
        self.assertEqual(plan('workflow_dispatch', requested=True), (True, True))
        self.assertEqual(plan('workflow_dispatch', requested=False), (True, False))
        self.assertEqual(plan('push', requested=True), (True, False))
        self.assertEqual(plan('push'), (True, False))

    def test_workflow_crons_match_gate_and_keep_daily_schedule(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/deploy.yml').read_text()
        crons = re.findall(r"^\s*- cron: '([^']+)'", workflow, re.MULTILINE)
        self.assertCountEqual(crons, ['0 13 * * *', '0 22 * * *',
                                      '0 14 * * 5', '0 15 * * 5'])
        self.assertEqual(set(crons) - {'0 13 * * *', '0 22 * * *'}, WEEKLY_CRONS)


if __name__ == '__main__':
    unittest.main()
