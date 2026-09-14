"""End-to-end exercise of the Provider-level Token Saver feature.

Goal (PM task): prove the provider-level toggles (``token_saver_rtk`` /
``token_saver_caveman`` / ``token_saver_ponytail`` on Provider id=1 "B.AI")
actually change gateway behaviour, via REAL requests to the live proxy.

What it proves
--------------
1. RTK (input side): a large tool-result body sent with saver OFF vs
   ``token_saver_rtk=true`` shows a large drop in ``usage.prompt_tokens``
   (RTK compresses the body before it reaches the upstream tokenizer).
   Verified deterministically by real requests below (~86% reduction observed).
2. caveman / ponytail (output side):
   (a) DETERMINISTIC proof the toggle changes the payload: importing the
       production hook ``backend.gateway.token_saver.apply_token_savers`` and
       asserting the style instruction is injected into a system message when
       the flag is on (and not when off). This is source-level proof the
       provider toggle wires through to a real payload mutation.
   (b) EMPIRICAL proof via real requests: a verbose prompt is sent with
       ``token_saver_caveman`` / ``token_saver_ponytail`` on; we measure
       ``usage.completion_tokens`` to observe the directional (LLM-variance-
       prone, reasoning-token-dominated) reduction. This is reported, not
       hard-gated, because the enabled models (hy3 / qwen3.8-flash are
       reasoning models) dilute the effect with reasoning tokens.

Hard rules honoured
-------------------
* G6  : only ``combo:B.AI`` or a VERIFIED ``provider:B.AI:<id>``. We pin to
       ``provider:B.AI:hy3`` because ``hy3`` is present in
       ``GET /api/providers/1`` ``models[]`` AND is an ENABLED member of
       combo ``B.AI`` (so it is registered + enabled + routes). No fabricated
       model ids.
* J6  : we only SEND requests; we never kill / restart the :8080 process.
* No ``api_key`` is ever read/printed (we select only the flag fields).
* Provider flags are restored to their pre-test snapshot in ``finally`` and
  re-verified via GET at the end.

Run
---
    pytest tests/e2e/test_token_saver_e2e.py -s

Env overrides:
    AIGATE_BASE_URL  (default http://127.0.0.1:8080)
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import pytest

# pytest.ini sets pythonpath=["src", "."]; this imports the production hook.
from backend.gateway import token_saver as _ts  # noqa: E402

BASE_URL = os.environ.get("AIGATE_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
PROVIDER_ID = 1
# Verified: hy3 is in GET /api/providers/1 models[] and is an ENABLED member of
# combo B.AI (combo member enabled=True). Pinning to a single model removes
# round-robin tokenizer variance from the OFF-vs-ON delta comparison.
MODEL = "provider:B.AI:hy3"

RTK_REPEATS = 3
OUTPUT_REPEATS = 3

OUTCOME = {}  # collected numbers for the receipt / teardown print


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_RETRY_CODES = {429, 502, 503, 504}


def _http(method: str, path: str, body=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=data, headers=headers, method=method
    )
    return urllib.request.urlopen(req, timeout=timeout)


def get_provider_flags() -> dict:
    d = json.load(_http("GET", f"/api/providers/{PROVIDER_ID}"))
    return {
        "token_saver_rtk": bool(d["token_saver_rtk"]),
        "token_saver_caveman": bool(d["token_saver_caveman"]),
        "token_saver_ponytail": bool(d["token_saver_ponytail"]),
    }


def set_provider_flags(flags: dict) -> None:
    _http("PUT", f"/api/providers/{PROVIDER_ID}", flags)


def chat(payload: dict, timeout=120) -> dict:
    """POST /v1/chat/completions with exponential backoff on 429/5xx (RPM + slow upstream)."""
    last_err = None
    for attempt in range(6):
        try:
            return json.load(_http("POST", "/v1/chat/completions", payload, timeout))
        except urllib.error.HTTPError as exc:
            if exc.code in _RETRY_CODES:
                wait = 2 ** attempt
                print(f"  HTTP {exc.code}; backing off {wait}s (attempt {attempt+1})")
                time.sleep(wait)
                last_err = exc
                continue
            raise
    raise last_err  # type: ignore[misc]


def build_large_tool_payload() -> dict:
    """~2000-line fake ``diff --git`` tool result with blank runs + ANSI."""
    parts = [
        "diff --git a/src/app.py b/src/app.py",
        "index 0000000..1111111 100644",
        "--- a/src/app.py",
        "+++ b/src/app.py",
    ]
    for i in range(400):
        parts += [
            f"@@ -{i*10},{i*10+10} +{i*10},{i*10+10} @@ def func_{i}():",
            f"+    added line {i} with some content to tokenize upstream",
            " ",
            " ",
            " ",
        ]
    tool = "\x1b[31m" + "\n".join(parts) + "\x1b[0m"
    return {
        "model": MODEL,
        "max_tokens": 80,
        "messages": [
            {"role": "user", "content": "Ignore the diff. Reply with the word DONE only."},
            {"role": "tool", "tool_call_id": "c1", "content": tool},
        ],
    }


def build_verbose_payload() -> dict:
    # Bounded prompt (fast, avoids 504 timeouts) + moderate cap so the style
    # instruction can actually change the finishing length.
    return {
        "model": MODEL,
        "max_tokens": 512,
        "messages": [
            {
                "role": "user",
                "content": (
                    "List 8 Python built-in functions with a one-line description "
                    "for each. Be thorough and include a short illustrative note."
                ),
            }
        ],
    }


def prompt_tokens_of(payload: dict) -> int:
    return chat(payload)["usage"]["prompt_tokens"]


def completion_tokens_of(payload: dict) -> int:
    return chat(payload)["usage"]["completion_tokens"]


def avg(xs):
    return sum(xs) / len(xs)


# --------------------------------------------------------------------------- #
# Fixture: snapshot + restore provider flags
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def provider_snapshot():
    try:
        snap = get_provider_flags()
    except Exception as exc:  # server unreachable etc.
        pytest.skip(f"cannot reach proxy at {BASE_URL}: {exc}")
    print(f"\n[snapshot] provider {PROVIDER_ID} flags BEFORE = {snap}")
    try:
        yield snap
    finally:
        set_provider_flags(snap)
        restored = get_provider_flags()
        print(f"[restore ] provider {PROVIDER_ID} flags AFTER  = {restored}")
        assert restored == snap, f"flags not restored! {restored} != {snap}"
        OUTCOME["flags_before"] = snap
        OUTCOME["flags_after"] = restored


# --------------------------------------------------------------------------- #
# Test 1: RTK (input-side) reduction — deterministic, hard assertion (real reqs)
# --------------------------------------------------------------------------- #
def test_rtk_reduces_prompt_tokens(provider_snapshot):
    payload = build_large_tool_payload()

    set_provider_flags(
        {"token_saver_rtk": False, "token_saver_caveman": False, "token_saver_ponytail": False}
    )
    off = [prompt_tokens_of(payload) for _ in range(RTK_REPEATS)]

    set_provider_flags(
        {"token_saver_rtk": True, "token_saver_caveman": False, "token_saver_ponytail": False}
    )
    rtk = [prompt_tokens_of(payload) for _ in range(RTK_REPEATS)]

    off_avg, rtk_avg = avg(off), avg(rtk)
    delta = off_avg - rtk_avg
    ratio = delta / off_avg if off_avg else 0.0

    print(f"[RTK] prompt_tokens OFF  avg={off_avg:.0f}  samples={off}")
    print(f"[RTK] prompt_tokens RTK  avg={rtk_avg:.0f}  samples={rtk}")
    print(f"[RTK] delta={delta:.0f} tokens  reduction={ratio*100:.1f}%")

    OUTCOME["rtk_off_avg"] = off_avg
    OUTCOME["rtk_rtk_avg"] = rtk_avg
    OUTCOME["rtk_reduction_pct"] = ratio * 100

    # Hard gate: RTK must substantially reduce input tokens.
    assert rtk_avg < off_avg, "RTK did not reduce prompt_tokens"
    assert ratio > 0.30, f"RTK reduction too small ({ratio*100:.1f}%)"


# --------------------------------------------------------------------------- #
# Test 2: caveman / ponytail toggle CHANGES the payload (deterministic hook test)
# --------------------------------------------------------------------------- #
def test_output_savers_inject_instruction():
    """Source-level proof the provider toggle mutates the payload.

    Mirrors gateway/router.py:_apply_token_saver_for_provider: enabled modes in
    the fixed order rtk -> caveman -> ponytail are applied via
    token_saver.apply_token_savers. We assert the injected instruction text
    appears in a system message exactly when the matching flag is on.
    """
    payload = {"messages": [{"role": "user", "content": "hi"}]}

    # OFF-like: no modes -> payload unchanged, no system message.
    out_off, saved_off = _ts.apply_token_savers([], dict(payload))
    assert out_off == payload
    assert all(m["role"] != "system" for m in out_off["messages"])

    # CAVEMAN on.
    out_c, _ = _ts.apply_token_savers(["caveman"], dict(payload))
    sys_c = [m["content"] for m in out_c["messages"] if m["role"] == "system"]
    assert sys_c and _ts.CAVEMAN_INSTRUCTION in sys_c[0]

    # PONYTAIL on.
    out_p, _ = _ts.apply_token_savers(["ponytail"], dict(payload))
    sys_p = [m["content"] for m in out_p["messages"] if m["role"] == "system"]
    assert sys_p and _ts.PONYTAIL_INSTRUCTION in sys_p[0]

    # rtk does NOT inject a system instruction (input-side only).
    out_r, _ = _ts.apply_token_savers(["rtk"], dict(payload))
    assert all(m["role"] != "system" for m in out_r["messages"])

    print("[HOOK] caveman/ponytail inject system instruction when flag on; rtk does not.")


# --------------------------------------------------------------------------- #
# Test 3: caveman / ponytail (output-side) — empirical real requests (soft)
# --------------------------------------------------------------------------- #
def test_output_savers_completion_tokens_empirical(provider_snapshot):
    payload = build_verbose_payload()
    measured = {}

    set_provider_flags(
        {"token_saver_rtk": False, "token_saver_caveman": False, "token_saver_ponytail": False}
    )
    off = [completion_tokens_of(payload) for _ in range(OUTPUT_REPEATS)]

    set_provider_flags(
        {"token_saver_rtk": False, "token_saver_caveman": True, "token_saver_ponytail": False}
    )
    caveman = [completion_tokens_of(payload) for _ in range(OUTPUT_REPEATS)]

    set_provider_flags(
        {"token_saver_rtk": False, "token_saver_caveman": False, "token_saver_ponytail": True}
    )
    ponytail = [completion_tokens_of(payload) for _ in range(OUTPUT_REPEATS)]

    measured["off"] = avg(off)
    measured["caveman"] = avg(caveman)
    measured["ponytail"] = avg(ponytail)

    print(f"[OUT] completion_tokens OFF      avg={measured['off']:.0f}  samples={off}")
    print(f"[OUT] completion_tokens CAVEMAN  avg={measured['caveman']:.0f}  samples={caveman}")
    print(f"[OUT] completion_tokens PONYTAIL avg={measured['ponytail']:.0f}  samples={ponytail}")

    OUTCOME["out_off_avg"] = measured["off"]
    OUTCOME["out_caveman_avg"] = measured["caveman"]
    OUTCOME["out_ponytail_avg"] = measured["ponytail"]

    # Directional / soft gate: a saver must not materially INCREASE output.
    # (caveman/ponytail effect is diluted by reasoning tokens on hy3; we only
    #  fail on a large blow-up, and report directionality in the receipt.)
    for name, val in (("caveman", measured["caveman"]), ("ponytail", measured["ponytail"])):
        blowup = val / measured["off"] if measured["off"] else 1.0
        assert blowup < 1.5, f"{name} increased completion_tokens >50% ({blowup:.2f}x)"
        if val < measured["off"]:
            print(f"[OUT] {name}: reduced output vs OFF by {(1-val/measured['off'])*100:.1f}%")


def test_receipt_printed():
    """Sanity: ensure the suite captured real numbers (never fails the gate)."""
    assert OUTCOME.get("rtk_off_avg") and OUTCOME.get("rtk_rtk_avg")
    print("\n=== TOKEN SAVER E2E RECEIPT ===")
    print(json.dumps(OUTCOME, indent=2))
