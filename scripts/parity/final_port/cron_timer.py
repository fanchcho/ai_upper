"""Wait for a real UTC cron minute; no clock monkeypatch."""
import json,os,sys,uuid,time
from pathlib import Path
from datetime import datetime,timezone
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication
from mvvm.services.scheduled_tasks import next_run
app=QGuiApplication([])
w,b,s,t,e,h=build(Path('/tmp/ai-upper-cron-'+uuid.uuid4().hex),'dark',text_stream('cron reply'))
api=b.tasksService();error=api.create('Cron evidence','Run at the real next minute','recurring','* * * * *','UTC','general');assert not error,error
row=api.list()[0];delay=row['nextRunAt']/1000-time.time();print('ACTUAL_SECONDS_TO_NEXT_MINUTE',delay,flush=True)
assert _pump(app,lambda:bool(api.list()[0]['runs']),delay+8)
row=api.list()[0];assert row['runs'][0]['status']=='done';assert row['nextRunAt']>row['lastRunAt']
checks=[]
for name,cron,zone,at in [('weekday','0 10 * * 1','UTC','2026-11-27T00:00:00+00:00'),('dst_gap','30 2 * * *','America/New_York','2026-03-08T05:00:00+00:00'),('dst_fold','30 1 * * *','America/New_York','2026-11-01T04:00:00+00:00')]:
 value=next_run({'kind':'recurring','cron':cron,'tz':zone},datetime.fromisoformat(at).timestamp());checks.append([name,datetime.fromtimestamp(value,timezone.utc).isoformat()])
assert checks[0][1]=='2026-11-30T10:00:00+00:00'
assert checks[1][1]=='2026-03-09T06:30:00+00:00'
assert checks[2][1]=='2026-11-01T05:30:00+00:00'
try:next_run({'kind':'recurring','cron':'* * * * *','tz':'Invalid/Zone'});raise AssertionError('invalid zone accepted')
except KeyError:pass
Path('out/final-port/cron-timer.json').write_text(json.dumps({'real_clock_delay':delay,'row':row,'calendar_checks':checks,'invalid_zone_rejected':True},indent=2));print('PASS real cron timer, persisted history, weekday/DST and invalid-zone rejection',flush=True)
api.timer.stop();t.stop();w.close();e.deleteLater()
