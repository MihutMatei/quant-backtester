"""Dead man's switch ping.

healthchecks.io (or any ping-compatible endpoint) expects a ping after each
successful run and raises the alarm when one fails to arrive. It is the only
mechanism here that detects the bot being *absent* rather than *failing*:
systemd's OnFailure cannot fire on a machine that is switched off, and a
watchdog running beside the bot dies with it.

Everything here swallows its own errors. A missed ping costs a false alarm; an
exception escaping this module would cost a trading run. Monitoring must never
be able to take down the thing it monitors.

Uses urllib rather than requests: this is the last code that should acquire a
dependency, and requests is only present transitively via alpaca-py.
"""
import logging
import urllib.request

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5
MAX_BODY_BYTES = 10_000


def _ping(url, body=""):
    """POST to `url`. Returns True on success. Never raises."""
    if not url:
        return False
    try:
        data = body.encode("utf-8")[:MAX_BODY_BYTES] if body else b""
        request = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            response.read()
        return True
    except Exception as exc:
        # Deliberately broad: DNS, TLS, timeouts, HTTP errors, a malformed URL
        # in the config. None of them are worth failing a run over. The URL is
        # a credential, so it is not logged.
        log.warning("heartbeat ping failed: %s: %s", type(exc).__name__, exc)
        return False


def ok(url, summary=""):
    """Signal a healthy completed run. `summary` shows in the check's history."""
    return _ping(url, summary)


def fail(url, detail=""):
    """Signal a failed run, so the alert fires now rather than after the grace."""
    if not url:
        return False
    return _ping(url.rstrip("/") + "/fail", detail)
