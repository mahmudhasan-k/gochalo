"""All pytest verification is offline; Windows asyncio may use loopback."""
import ipaddress
import socket
import sys
from pathlib import Path
import pytest
root=Path(__file__).resolve().parent
sys.path[:0]=[str(root),str(root/"engine")]

@pytest.fixture(autouse=True)
def forbid_external_connections(monkeypatch):
    # A developer's root .env must never select live providers in offline tests.
    for name in ("GEMINI_API_KEY","GEMINI_BACKUP_API_KEY_1","GEMINI_BACKUP_API_KEY_2","GEMINI_MODEL","GEMINI_FALLBACK_MODEL",
                 "OPENROUTER_API_KEY","OPENROUTER_MODEL","GROQ_API_KEY","GROQ_MODEL",
                 "DETERMINISTIC_REVIEW_FALLBACK","GEMINI_RESEARCH_MODEL","RESEARCH_FREE_ACCESS_CONFIRMED","LOCAL_EVALUATION_CAPTURE"):
        monkeypatch.delenv(name,raising=False)
    from gemini_requests import reset_cooldowns
    reset_cooldowns()
    original=socket.socket.connect
    def connect(sock,address):
        if isinstance(address,tuple):
            try:
                if ipaddress.ip_address(address[0]).is_loopback:
                    return original(sock,address)
            except ValueError:
                pass
        raise AssertionError("Offline test attempted an external connection")
    monkeypatch.setattr(socket.socket,"connect",connect)
