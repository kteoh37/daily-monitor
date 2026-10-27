from datetime import datetime,timezone
import unittest
from portfolio_schedule import plan

class ScheduleTests(unittest.TestCase):
 def test_dst_and_standard_time(self):
  for day,active in [('2026-07-09','14'),('2026-12-10','15')]:
   for hour in ['14','15']:
    # Runner may start late; intended cron time still selects exactly one UTC candidate.
    result=plan('schedule',f'0 {hour} * * 4',now=datetime.fromisoformat(day+'T16:30:00+00:00'))
    self.assertEqual(result,(hour==active,hour==active))
 def test_preserves_daily_and_manual(self):
  self.assertEqual(plan('schedule','0 13 * * *'),(True,False))
  self.assertEqual(plan('schedule','0 22 * * *'),(True,False))
  self.assertEqual(plan('workflow_dispatch',requested=True),(True,True))
  self.assertEqual(plan('push'),(True,False))
if __name__=='__main__':unittest.main()
