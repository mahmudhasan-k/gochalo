"""Server-only local configuration; process environment always takes precedence."""
import os
import re
from pathlib import Path

def load_local_env(path=None):
    if os.environ.get("APP_ENV", "development").lower() in {"production", "prod"}:
        return
    env_path=Path(path) if path else Path(__file__).resolve().parents[2]/".env"
    try:
        lines=env_path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line=line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line=line[7:].strip()
        key,separator,value=line.partition("=")
        key=key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",key):
            continue
        value=value.strip()
        if value.startswith(("'",'"')):
            if len(value)<2 or value[-1]!=value[0]:
                continue
            value=value[1:-1]
        else:
            value=re.split(r"\s+#",value,maxsplit=1)[0].rstrip()
        # No shell evaluation, interpolation, logging or overwriting host secrets.
        os.environ.setdefault(key,value)

load_local_env()
# Kept for old adapter compatibility; new routes require an explicit model/key.
OPENROUTER_FALLBACK_ENABLED = False

DETERMINISTIC_REVIEW_FALLBACK = True

def deterministic_review_enabled():
    """Fail closed only on an explicit owner opt-out; blank inherits the default."""
    default = "true" if DETERMINISTIC_REVIEW_FALLBACK else "false"
    return os.environ.get("DETERMINISTIC_REVIEW_FALLBACK", default).strip().lower() not in {"false", "0", "off", "no"}
