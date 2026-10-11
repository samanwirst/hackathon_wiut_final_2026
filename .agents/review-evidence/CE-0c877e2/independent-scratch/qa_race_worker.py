"""QA_ONLY SQL schedule injection over the unchanged production ASGI app."""
import os,time,contextvars
from pathlib import Path
from sqlalchemy import event,Engine
from app.main import app
pause=contextvars.ContextVar('qa_pause_reservation',default=False)
root=Path('/tmp/visionflow-m3-emergency-review-0c877e2')
@app.middleware('http')
async def identify(request,call_next):
    token=pause.set(request.headers.get('X-QA-Pause')=='yes')
    try:
        r=await call_next(request);r.headers['X-QA-Worker']=str(os.getpid());return r
    finally:pause.reset(token)
@event.listens_for(Engine,'before_cursor_execute')
def sql_gap(conn,cursor,statement,parameters,context,executemany):
    if pause.get() and 'ORDER BY autolearn_labeling_reservations.slot DESC' in statement:
        (root/'worker-paused.json').write_text(str(os.getpid()))
        start=time.monotonic()
        while not (root/'worker-resume').exists():
            if time.monotonic()-start>8:raise RuntimeError('QA_ONLY scheduling wait expired')
            time.sleep(.01)
