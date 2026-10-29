"""Opt-in, bounded in-memory local evaluation traces. Never log credentials."""
from contextvars import ContextVar
import hashlib
import json
import os

sink = ContextVar("evaluation_trace", default=None)
MAX_BYTES = 1024 * 1024


def record(stage, **data):
    trace = sink.get()
    if trace is None:
        return
    def safe(value):
        if isinstance(value, str):
            for key in ("GEMINI_API_KEY","GEMINI_BACKUP_API_KEY_1","GEMINI_BACKUP_API_KEY_2",
                        "OPENROUTER_API_KEY","GROQ_API_KEY"):
                secret = os.environ.get(key, "").strip()
                if secret:
                    value = value.replace(secret, "[credential omitted]")
            return value
        if isinstance(value, bytes):
            return {"bytes":len(value),"sha256":hashlib.sha256(value).hexdigest()}
        if isinstance(value, dict):
            return {k:safe(v) for k,v in value.items() if k.casefold() not in {"headers","api_key","authorization"}}
        if isinstance(value, (list,tuple)):
            return [safe(v) for v in value]
        if hasattr(value, "model_dump"):
            return safe(value.model_dump(exclude_none=True))
        return value
    event = {"stage":stage, **safe(data)}
    size = len(json.dumps(event,ensure_ascii=False).encode())
    used = sum(len(json.dumps(e,ensure_ascii=False).encode()) for e in trace)
    if used + size <= MAX_BYTES:
        trace.append(event)
    elif not any(e.get("coverage") == "trace_size_limit" for e in trace):
        trace.append({"stage":stage,"coverage":"trace_size_limit","omitted_bytes":size})
