import asyncio
import faulthandler
import sys
import threading
import os
import pytest

faulthandler.enable()
if '--heartbeat' in sys.argv:
    sys.argv.remove('--heartbeat')
    original_run_forever = asyncio.BaseEventLoop.run_forever
    def qa_run_forever(self):
        def qa_heartbeat():
            if not self.is_closed():
                self.call_later(0.01, qa_heartbeat)
        self.call_soon(qa_heartbeat)
        return original_run_forever(self)
    asyncio.BaseEventLoop.run_forever = qa_run_forever
    print('QA ONLY: temporary 10 ms asyncio heartbeat enabled; production code unchanged', flush=True)
    def watchdog():
        faulthandler.dump_traceback()
        os._exit(124)
    timer = threading.Timer(50, watchdog)
    timer.daemon = True
    timer.start()
else:
    faulthandler.dump_traceback_later(8, exit=True)
raise SystemExit(pytest.main(sys.argv[1:]))
