"""CORS: the browser frontend may call the API from its own origin, and only from allowed ones."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ALLOWED = "http://localhost:5173"


def preflight(origin: str, headers: str = "authorization,content-type,idempotency-key"):
    return client.options("/health", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": headers})


def test_an_allowed_origin_passes_the_preflight():
    r = preflight(ALLOWED)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == ALLOWED
    assert "POST" in r.headers["access-control-allow-methods"]
    allowed = r.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed and "idempotency-key" in allowed


def test_a_simple_request_from_an_allowed_origin_gets_the_header():
    r = client.get("/health", headers={"Origin": ALLOWED})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == ALLOWED


def test_an_unknown_origin_is_not_allowed():
    assert preflight("https://evil.example").status_code == 400
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
