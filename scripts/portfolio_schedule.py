"""DST-safe Thursday 10:00 New York gate for the two UTC cron candidates."""
from datetime import datetime, timezone
import os
from zoneinfo import ZoneInfo

WEEKLY_CRONS={'0 14 * * 4','0 15 * * 4'}

def plan(event, cron='', requested=False, now=None):
    now=now or datetime.now(timezone.utc)
    if event=='schedule' and cron in WEEKLY_CRONS:
        # Interpret intended cron hour, not actual delayed runner start hour.
        intended=now.astimezone(timezone.utc).replace(hour=int(cron.split()[1]),minute=0,second=0,microsecond=0)
        local=intended.astimezone(ZoneInfo('America/New_York'))
        selected=local.weekday()==3 and local.hour==10
        return selected,selected
    return True,bool(requested and event=='workflow_dispatch')

if __name__=='__main__':
    run,refresh=plan(os.environ['EVENT_NAME'],os.environ.get('CRON',''),os.environ.get('REQUESTED')=='true')
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:
        f.write(f'run={str(run).lower()}\nrefresh={str(refresh).lower()}\n')
