"""QA_ONLY response header wrapper around unchanged production app."""
import os,threading
from app.main import app
@app.middleware('http')
async def identify_worker(request,call_next):
    response=await call_next(request)
    response.headers['X-QA-Worker']=str(os.getpid())
    return response
