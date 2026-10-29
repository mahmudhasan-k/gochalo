"""Local admission does not depend on provider quotas or caller-supplied proxy headers."""
from unittest.mock import patch
from fastapi.testclient import TestClient
import main
from session_admission import SessionAdmission


def test_peer_limit_recovers_after_window_and_drops_old_peers():
    now = [0]
    guard = SessionAdmission(clock=lambda: now[0], per_peer=2, total=4)
    assert guard.reserve("one") == guard.reserve("one") == 0
    assert guard.reserve("one") == 60
    assert guard.reserve("two") == 0
    now[0] = 61
    assert guard.reserve("three") == 0
    assert set(guard.peers) == {"three"}


def test_global_limit_bounds_peer_buckets_without_eviction_bypass():
    guard = SessionAdmission(clock=lambda: 0, per_peer=2, total=3)
    for i in range(3):
        assert guard.reserve(str(i)) == 0
    assert guard.reserve("different") == 60
    assert len(guard.peers) == len(guard.recent) == 3


def test_forwarded_header_does_not_reset_client_admission_or_touch_existing_tokens():
    with TestClient(main.app) as client, patch.object(main, "session_admission", SessionAdmission(per_peer=2)):
        first = client.post("/api/session").json()["token"]
        assert client.post("/api/session", headers={"X-Forwarded-For":"203.0.113.1"}).status_code == 200
        blocked = client.post("/api/session", headers={"X-Forwarded-For":"203.0.113.2"})
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
        assert "no-store" in blocked.headers["Cache-Control"]
        assert main.session(first)


def test_static_compression_and_immutable_cache_do_not_apply_to_private_api():
    if not main.static_root.is_dir():
        return  # Source-only backend checkout: production assets are built separately.
    with TestClient(main.app) as client:
        asset = next((main.static_root / "assets").glob("*.css"))
        response = client.get("/assets/" + asset.name, headers={"Accept-Encoding":"gzip"})
        assert response.headers["Content-Encoding"] == "gzip"
        assert "immutable" in response.headers["Cache-Control"]
        assert client.get("/").headers["Cache-Control"] == "no-cache"
        api = client.get("/api/health", headers={"Accept-Encoding":"gzip"})
        assert "Content-Encoding" not in api.headers
        assert "no-store" in api.headers["Cache-Control"]
