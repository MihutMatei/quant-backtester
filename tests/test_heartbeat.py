"""The heartbeat must never be able to break a trading run."""
import urllib.error

import pytest

from bot import heartbeat

URL = "https://hc-ping.com/deadbeef-0000-0000-0000-000000000000"


class Recorder:
    """Stands in for urlopen, capturing what would have been sent."""

    def __init__(self, raises=None):
        self.raises, self.calls = raises, []

    def __call__(self, request, timeout=None):
        self.calls.append((request.full_url, request.data, request.method, timeout))
        if self.raises:
            raise self.raises
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"OK"


@pytest.fixture
def urlopen(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(heartbeat.urllib.request, "urlopen", rec)
    return rec


class TestDisabled:
    """Unset URL is the default; it must cost nothing."""

    def test_ok_is_a_noop_without_a_url(self, urlopen):
        assert heartbeat.ok("", "summary") is False
        assert urlopen.calls == []

    def test_fail_is_a_noop_without_a_url(self, urlopen):
        assert heartbeat.fail("", "boom") is False
        assert urlopen.calls == []

    def test_none_url_does_not_raise(self, urlopen):
        assert heartbeat.ok(None) is False
        assert urlopen.calls == []


class TestPinging:
    def test_ok_posts_to_the_url(self, urlopen):
        assert heartbeat.ok(URL, "no action") is True
        url, data, method, timeout = urlopen.calls[0]
        assert url == URL
        assert method == "POST"
        assert data == b"no action"

    def test_fail_posts_to_the_fail_endpoint(self, urlopen):
        assert heartbeat.fail(URL, "traceback") is True
        assert urlopen.calls[0][0] == URL + "/fail"

    def test_fail_does_not_double_the_slash(self, urlopen):
        heartbeat.fail(URL + "/", "x")
        assert urlopen.calls[0][0] == URL + "/fail"

    def test_a_timeout_is_always_set(self, urlopen):
        # A hanging endpoint must not stall the run.
        heartbeat.ok(URL)
        assert urlopen.calls[0][3] == heartbeat.TIMEOUT_SECONDS

    def test_empty_summary_sends_no_body(self, urlopen):
        heartbeat.ok(URL)
        assert urlopen.calls[0][1] == b""

    def test_oversized_body_is_truncated(self, urlopen):
        heartbeat.ok(URL, "x" * 50_000)
        assert len(urlopen.calls[0][1]) == heartbeat.MAX_BODY_BYTES


class TestNeverRaises:
    """Every one of these would otherwise kill a trading run."""

    @pytest.mark.parametrize("error", [
        urllib.error.URLError("dns failure"),
        urllib.error.HTTPError(URL, 500, "server error", {}, None),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        ValueError("unknown url type"),      # malformed URL in the config
        OSError("network unreachable"),
    ])
    def test_network_errors_are_swallowed(self, monkeypatch, error):
        monkeypatch.setattr(heartbeat.urllib.request, "urlopen", Recorder(raises=error))
        assert heartbeat.ok(URL, "summary") is False
        assert heartbeat.fail(URL, "detail") is False

    def test_the_url_is_not_logged(self, monkeypatch, caplog):
        # The ping URL is a credential: leaking it into journald would let a
        # reader suppress the alert.
        monkeypatch.setattr(heartbeat.urllib.request, "urlopen",
                            Recorder(raises=urllib.error.URLError("nope")))
        heartbeat.ok(URL, "summary")
        assert "deadbeef" not in caplog.text
