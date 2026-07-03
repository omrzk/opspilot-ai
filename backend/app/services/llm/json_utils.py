"""Robust extraction of JSON objects from LLM output.

LLMs wrap JSON in code fences, add prose around it, and occasionally emit raw
control characters inside string literals. This module recovers a parseable
object from all of those, or raises ValueError with the offending text."""

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _find_balanced_object(text: str) -> str | None:
    """Return the first balanced top-level {...} in text, honoring strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _escape_control_chars_in_strings(text: str) -> str:
    """Escape raw newlines/tabs/control chars that appear inside string literals."""
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                in_string = False
                out.append(ch)
                continue
            code = ord(ch)
            if code < 0x20:
                out.append(
                    {0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r"}.get(
                        code, f"\\u{code:04x}"
                    )
                )
                continue
            out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def extract_json_object(text: str) -> dict:
    """Parse the first JSON object found in an LLM response."""
    candidates: list[str] = []
    for fenced in _FENCE_RE.findall(text):
        candidates.append(fenced.strip())
    candidates.append(text.strip())
    balanced = _find_balanced_object(text)
    if balanced:
        candidates.append(balanced)

    last_error: Exception | None = None
    for candidate in candidates:
        inner = _find_balanced_object(candidate) or candidate
        for attempt in (inner, _escape_control_chars_in_strings(inner)):
            try:
                parsed = json.loads(attempt)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue
            if isinstance(parsed, dict):
                return parsed
    raise ValueError(f"No JSON object found in LLM output: {last_error}")
