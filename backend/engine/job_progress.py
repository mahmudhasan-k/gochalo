"""Per-workflow progress callback, propagated through asyncio.to_thread."""
from contextvars import ContextVar
callback=ContextVar("job_progress",default=None)
def report(stage):
    listener=callback.get()
    if listener is not None:
        listener(stage)
