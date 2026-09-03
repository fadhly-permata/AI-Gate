"""Token Saver pre-translate hooks (ADR-013 / B5.4).

Applies a per-Endpoint ``token_saver`` mode to an incoming OpenAI-style chat
completion payload BEFORE it is forwarded to the upstream provider.

Modes
-----
* ``off``      -> payload returned unchanged.
* ``rtk``      -> compress tool-result-like content found in ``messages``
                 (git diff / grep / ls / tree / large code / stack traces);
                 fail-open, never drops normal conversation messages.
* ``caveman``  -> inject a concise/dense answer-style instruction into a system
                 message (create one if absent).
* ``ponytail`` -> inject a "write minimal code, reuse existing" instruction
                 into a system message (create one if absent).

ALL modes are **fail-open**: any exception inside a transform is caught,
logged to ``LogEntry`` via ``backend.log``, and the ORIGINAL payload is
returned unchanged. The hook must never raise into the gateway.

Pydantic: n/a (pure dict transforms). Rule R10 does not constrain this module.
"""

from __future__ import annotations

import re

from backend.log import log_info, log_warning_exc

# Allowed modes (mirrors TSD §4.6 / API contract §2.4.1).
TOKEN_SAVER_MODES = ("off", "rtk", "caveman", "ponytail")

# Injected instruction texts (EN). Kept verbatim for testability (keywords
# "concise"/"dense" and "minimal" are asserted by tests).
CAVEMAN_INSTRUCTION = (
    "Be concise and dense. Keep all technical substance; omit filler and "
    "pleasantries."
)
PONYTAIL_INSTRUCTION = (
    "Write minimal code. Reuse existing code; avoid unnecessary refactoring or "
    "new abstractions."
)

# ANSI escape sequence stripper (e.g. terminal colour codes in tool output).
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# Maintain a 200-head / 100-tail window per individual tool output.
_RTK_HEAD_LINES = 200
_RTK_TAIL_LINES = 100

# Fingerprints that mark a message body as a tool-result-like block worth
# compressing. A plain conversation message will not match these.
_TOOL_LIKE_MARKERS = (
    "git diff",
    "grep ",
    "tree ",
    "ls ",
    "diff --git",
    "index 0000000",
    "Traceback (most recent call last)",
    "drwxr-xr-x",
    "total ",
)


def apply_token_saver(mode: str, payload: dict) -> dict:
    """Apply ``mode`` to ``payload`` and return the (possibly) modified payload.

    Fail-open: on ANY exception the original ``payload`` is returned unchanged
    and the error is logged to ``LogEntry``. ``'off'`` / unknown modes also
    return the original payload untouched.
    """
    if mode in (None, "", "off") or mode not in TOKEN_SAVER_MODES:
        return payload
    try:
        if mode == "rtk":
            return _apply_rtk(payload)
        if mode == "caveman":
            return _apply_instruction(payload, CAVEMAN_INSTRUCTION)
        if mode == "ponytail":
            return _apply_instruction(payload, PONYTAIL_INSTRUCTION)
        return payload
    except Exception as exc:  # noqa: BLE001 - fail-open mandated by ADR-013
        log_warning_exc(
            f"token_saver mode '{mode}' failed; passing through original payload",
            source="backend.gateway.token_saver",
            exc=exc,
        )
        return payload


# --------------------------------------------------------------------------- #
# RTK: compress tool-result content
# --------------------------------------------------------------------------- #
def _is_tool_like(text: str) -> bool:
    """Heuristic: does this text body look like a tool result to compress?"""
    if not isinstance(text, str) or not text:
        return False
    low = text.lower()
    for marker in _TOOL_LIKE_MARKERS:
        if marker in text or marker in low:
            return True
    # Large block heuristic: very long bodies are almost always tool dumps.
    if len(text.split("\n")) > 100:
        return True
    return False


def _transform_text(text: str) -> str:
    """Collapse blank runs, strip ANSI, and truncate over-long output."""
    # Strip ANSI escape sequences.
    text = _ANSI_ESCAPE.sub("", text)
    # Per-line trailing whitespace trim (keeps indentation / code intact).
    lines = [ln.rstrip() for ln in text.split("\n")]

    # Truncate extremely long outputs: keep head + tail with a marker.
    total = len(lines)
    if total > _RTK_HEAD_LINES + _RTK_TAIL_LINES + 10:
        truncated = total - (_RTK_HEAD_LINES + _RTK_TAIL_LINES)
        lines = (
            lines[:_RTK_HEAD_LINES]
            + [f"[...truncated {truncated} lines...]"]
            + lines[-_RTK_TAIL_LINES:]
        )

    # Collapse 3+ consecutive blank lines into a single blank line.
    out: list[str] = []
    blank_run = False
    for ln in lines:
        if ln.strip() == "":
            if blank_run:
                continue  # already emitted one blank line for this run
            blank_run = True
            out.append(ln)
        else:
            blank_run = False
            out.append(ln)
    return "\n".join(out)


def _compress_content(role: str, content) -> object:
    """Return possibly-compressed ``content`` for a single message."""
    if isinstance(content, str):
        if role == "tool" or _is_tool_like(content):
            return _transform_text(content)
        return content
    if isinstance(content, list):
        new_parts = []
        for part in content:
            if (
                isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            ):
                if role == "tool" or _is_tool_like(part["text"]):
                    new_parts.append({**part, "text": _transform_text(part["text"])})
                else:
                    new_parts.append(part)
            else:
                new_parts.append(part)
        return new_parts
    return content


def _content_bytes(payload: dict) -> int:
    """Approximate byte size of all message content (for savings logging)."""
    if not isinstance(payload, dict):
        return 0
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return 0
    total = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            total += len(content.encode("utf-8"))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    total += len(part["text"].encode("utf-8"))
    return total


def _apply_rtk(payload: dict) -> dict:
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        return payload

    before = _content_bytes(payload)
    new_messages = []
    for msg in messages:
        if not isinstance(msg, dict):
            new_messages.append(msg)
            continue
        new_msg = dict(msg)  # shallow copy; do not mutate the caller's dict
        new_msg["content"] = _compress_content(msg.get("role"), msg.get("content"))
        new_messages.append(new_msg)

    new_payload = dict(payload)
    new_payload["messages"] = new_messages

    after = _content_bytes(new_payload)
    saved = before - after
    if saved > 0:
        log_info(
            f"token_saver rtk: approx {saved} bytes saved",
            source="backend.gateway.token_saver",
            context={"saved_bytes": saved},
        )
    return new_payload


# --------------------------------------------------------------------------- #
# Caveman / Ponytail: inject style instruction into a system message
# --------------------------------------------------------------------------- #
def _apply_instruction(payload: dict, instruction: str) -> dict:
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        return payload

    new_messages = list(messages)
    sys_idx = None
    for i, msg in enumerate(new_messages):
        if isinstance(msg, dict) and msg.get("role") == "system":
            sys_idx = i
            break

    if sys_idx is not None:
        msg = new_messages[sys_idx]
        content = msg.get("content")
        if isinstance(content, str):
            if instruction not in content:
                merged = content.rstrip()
                merged = merged + "\n\n" + instruction if merged else instruction
                new_msg = dict(msg)
                new_msg["content"] = merged
                new_messages[sys_idx] = new_msg
            # else: instruction already present; leave unchanged.
        else:
            # Non-string system content: prepend a fresh system message.
            new_messages.insert(sys_idx, {"role": "system", "content": instruction})
    else:
        # No system message: prepend one carrying the instruction.
        new_messages.insert(0, {"role": "system", "content": instruction})

    new_payload = dict(payload)
    new_payload["messages"] = new_messages
    return new_payload


__all__ = ["TOKEN_SAVER_MODES", "apply_token_saver"]
