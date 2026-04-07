"""User-facing API error messages for the Streamlit UI."""

from __future__ import annotations

import httpx


def format_api_error(exc: BaseException) -> str:
    if isinstance(exc, httpx.ConnectError):
        return (
            "Cannot connect to the API. Start the server "
            "(e.g. `python -m uvicorn backend.main:app --reload`) and check the API base URL in the sidebar."
        )
    if isinstance(exc, httpx.TimeoutException):
        return "The request timed out. Check your network or try again."
    if isinstance(exc, httpx.HTTPStatusError):
        return _format_http_status_error(exc)
    return str(exc) or type(exc).__name__


def _format_http_status_error(exc: httpx.HTTPStatusError) -> str:
    status = exc.response.status_code
    try:
        body = exc.response.json()
        detail = body.get("detail")
        if isinstance(detail, dict):
            code = detail.get("error") or ""
            msg = detail.get("message") or ""
            if code and msg:
                return f"{msg} (code: {code})"
            if msg:
                return str(msg)
            if code:
                return f"Error code: {code}"
        if isinstance(detail, list):
            parts: list[str] = []
            for item in detail:
                if isinstance(item, dict):
                    loc = item.get("loc") or ()
                    msg = item.get("msg") or ""
                    loc_s = ".".join(str(x) for x in loc if x != "body")
                    parts.append(f"{loc_s}: {msg}".strip(": ") if loc_s else msg)
                else:
                    parts.append(str(item))
            if parts:
                return f"Invalid input ({status}): " + "; ".join(parts)
        if isinstance(detail, str):
            return f"{detail} (HTTP {status})"
    except Exception:
        pass
    text = exc.response.text or ""
    if status == 401:
        return "Authentication failed (HTTP 401). Check OPENAI_API_KEY on the server."
    if status == 429:
        return "Rate limited (HTTP 429). Wait and try again."
    if status == 503:
        return (
            "Service unavailable (HTTP 503). Often missing API key or Weaviate down — "
            "check server logs and /ready."
        )
    snippet = text[:400].replace("\n", " ")
    return f"HTTP {status}" + (f": {snippet}" if snippet else "")
