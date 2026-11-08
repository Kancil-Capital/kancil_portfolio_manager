"""
The Alpha Vantage API key never reaches the logs (issue #15).
Runs _fetch_from_alpha_vantage against a local HTTP server, so no real AV call is made.
"""

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import services.eps_service as eps

KEY = "TESTKEY-DO-NOT-LOG-123"


@pytest.fixture
def av_server(monkeypatch):
    state = {"status": 200, "body": b'{"Note": "rate limited"}', "last_path": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["last_path"] = self.path
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(state["body"])

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(eps.settings, "alpha_vantage_api_key", KEY)
    monkeypatch.setattr(eps, "AV_BASE_URL", f"http://127.0.0.1:{server.server_port}/query")
    monkeypatch.setattr(eps, "_wait_for_av_slot", lambda: None)
    yield state
    server.shutdown()


def _logs(caplog):
    return "\n".join(r.getMessage() for r in caplog.records)


def test_key_is_still_sent_as_a_query_param(av_server):
    eps._fetch_from_alpha_vantage("NVDA")
    assert f"apikey={KEY}" in av_server["last_path"]
    assert "function=EARNINGS" in av_server["last_path"]
    assert "symbol=NVDA" in av_server["last_path"]


@pytest.mark.parametrize("status", [200, 404, 500, 503])
def test_key_not_logged_for_any_status(av_server, caplog, status):
    av_server["status"] = status
    with caplog.at_level(logging.DEBUG):
        assert eps._fetch_from_alpha_vantage("NVDA") == []
    assert KEY not in _logs(caplog)
    if status >= 400:
        assert f"HTTP {status}" in _logs(caplog)


def test_key_not_logged_on_connection_error(monkeypatch, caplog):
    monkeypatch.setattr(eps.settings, "alpha_vantage_api_key", KEY)
    monkeypatch.setattr(eps, "AV_BASE_URL", "http://127.0.0.1:1/query")
    monkeypatch.setattr(eps, "_wait_for_av_slot", lambda: None)
    with caplog.at_level(logging.DEBUG):
        assert eps._fetch_from_alpha_vantage("NVDA") == []
    assert KEY not in _logs(caplog)
    assert "ConnectError" in _logs(caplog)


def test_key_not_logged_on_bad_json(av_server, caplog):
    av_server["body"] = b"<html>not json</html>"
    with caplog.at_level(logging.DEBUG):
        assert eps._fetch_from_alpha_vantage("NVDA") == []
    assert KEY not in _logs(caplog)


def test_httpx_request_logging_is_silenced():
    # httpx logs every request URL (key included) at INFO
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
