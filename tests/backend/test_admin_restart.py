"""DEV-RESTART backend tests for ``POST /api/dev/restart`` (be-dev).

Covers the three contract guarantees from the handover:

(a) dev_mode OFF  -> 403 ``dev_mode_required`` and NO restart scheduled.
(b) dev_mode ON   -> 200 ``{"status":"restarting"}`` + a daemon timer scheduled
    with the correct argv (``[sys.executable, <abs run.py>, *user argv]``);
    firing the timer triggers ``os.execv``.
(c) the single-shot guard: a second call does NOT schedule a second timer.

SAFETY (rule J6 + handover): the real server is NEVER restarted here.
- ``os.execv`` is monkeypatched to a spy (no process image is replaced).
- ``backend.admin_router.Timer`` is replaced with a fake, so no real thread is
  spawned and the 0.6s interval is never waited on; the test fires the stored
  callback manually to prove the timer->execv wiring.

Client: the repo's ``TestClient`` fixture is broken in THIS environment by an
incompatible ``starlette 0.27 + httpx 0.28`` pair (see ``test_chat_router.py``).
We therefore drive the app with ``httpx.ASGITransport`` (the faithful in-process
ASGI equivalent) and never reach a live server or the user's ``:8080``.

DB isolation: conftest has already redirected ``AIGATE_DB_PATH`` to a throwaway
temp file and created the schema; ``dev_mode`` is written via the settings repo.
"""

from __future__ import annotations

import os
import sys

import httpx
import pytest

import backend.admin_router as admin_router
from backend.config.settings import set as set_setting
from backend.server import app


@pytest.fixture
async def client():
    """In-process async ASGI client (no socket, no live server loopback)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """Force a known-clean state per test: guard reset + dev_mode OFF.

    The session temp DB persists across tests, so dev_mode could leak; we pin it
    to ``"false"`` at each test start (tests that need ON override it locally).
    """
    monkeypatch.setattr(admin_router, "_restart_scheduled", False)
    set_setting("dev_mode", "false")
    yield


@pytest.fixture
def fake_timers(monkeypatch):
    """Replace ``admin_router.Timer`` with a fake that records instances.

    No real thread is started; each instance keeps its callback + args so a test
    can fire it manually and assert the execv wiring.
    """
    created: list["_FakeTimer"] = []

    class _FakeTimer:
        def __init__(self, interval, function, args=None, kwargs=None):
            self.interval = interval
            self.function = function
            self.args = args or ()
            self.kwargs = kwargs or {}
            self.daemon = False
            self.started = False
            created.append(self)

        def start(self) -> None:
            self.started = True

        def cancel(self) -> None:  # pragma: no cover - parity with threading.Timer
            pass

        def fire(self):
            return self.function(*self.args, **self.kwargs)

    monkeypatch.setattr(admin_router, "Timer", _FakeTimer)
    return created


@pytest.fixture
def execv_calls(monkeypatch):
    """Patch ``os.execv`` to a spy so nothing is ever really re-execed."""
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(os, "execv", lambda path, argv: calls.append((path, list(argv))))
    return calls


# --------------------------------------------------------------------------- #
# (a) dev_mode OFF -> 403, nothing scheduled, nothing exec'd
# --------------------------------------------------------------------------- #
async def test_dev_off_returns_403_and_schedules_nothing(client, fake_timers, execv_calls):
    r = await client.post("/api/dev/restart")
    assert r.status_code == 403, r.text
    err = r.json()["error"]
    assert err["code"] == "dev_mode_required"
    assert err["type"] == "invalid_request_error"
    assert err["message"] == "developer mode is off"
    # No timer created and no execv attempted.
    assert fake_timers == []
    assert execv_calls == []


async def test_missing_dev_mode_is_treated_off(client, fake_timers, execv_calls, monkeypatch):
    """A read that yields None (missing key) must fail closed to 403."""
    monkeypatch.setattr(admin_router, "get_setting", lambda *a, **k: None)
    r = await client.post("/api/dev/restart")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "dev_mode_required"
    assert fake_timers == []
    assert execv_calls == []


# --------------------------------------------------------------------------- #
# (b) dev_mode ON -> 200, one daemon timer with correct argv, timer fires execv
# --------------------------------------------------------------------------- #
async def test_dev_on_returns_200_and_schedules_execv(
    client, fake_timers, execv_calls, monkeypatch
):
    # Simulate a server launched as: python run.py --port 9000
    monkeypatch.setattr(sys, "argv", ["run.py", "--port", "9000"])
    set_setting("dev_mode", "true")

    r = await client.post("/api/dev/restart")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "restarting"}

    # Exactly one timer, on the configured delay, as a daemon, started.
    assert len(fake_timers) == 1
    timer = fake_timers[0]
    assert timer.interval == admin_router.RESTART_DELAY_S == 0.6
    assert timer.daemon is True
    assert timer.started is True

    # execv must NOT have fired yet — the response is returned first.
    assert execv_calls == []

    # Firing the timer performs the in-process re-exec with the reconstructed argv.
    timer.fire()
    assert len(execv_calls) == 1
    path, argv = execv_calls[0]
    assert path == sys.executable
    assert argv[0] == sys.executable
    # run.py resolved to an ABSOLUTE path that exists in the repo.
    assert os.path.isabs(argv[1])
    assert argv[1].endswith("run.py")
    assert os.path.isfile(argv[1])
    # The user's launch args are preserved verbatim.
    assert argv[2:] == ["--port", "9000"]


async def test_execv_arg_is_run_py_absolute_even_if_cwd_varies(monkeypatch, tmp_path):
    """Path resolution is derived from module location, not caller cwd."""
    derived = admin_router._resolve_run_py()
    assert os.path.isabs(derived) and derived.endswith("run.py")
    assert os.path.isfile(derived)


# --------------------------------------------------------------------------- #
# (c) single-shot guard: a second call must not schedule a second restart
# --------------------------------------------------------------------------- #
async def test_guard_prevents_double_schedule(client, fake_timers, execv_calls):
    set_setting("dev_mode", "true")

    first = await client.post("/api/dev/restart")
    second = await client.post("/api/dev/restart")
    third = await client.post("/api/dev/restart")

    # All still report "restarting" to the client (the process IS restarting).
    assert first.status_code == second.status_code == third.status_code == 200
    # But only ONE timer was ever scheduled.
    assert len(fake_timers) == 1
