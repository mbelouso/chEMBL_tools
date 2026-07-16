import io
import os
import random
import tarfile
import time
from collections.abc import Callable
import requests


_BASE = os.getenv("COLABFOLD_API_BASE", "https://api.colabfold.com")
_FALLBACK_BASE = os.getenv("COLABFOLD_API_FALLBACK_BASE", "https://a3m.mmseqs.com")
_USER_AGENT = os.getenv(
    "COLABFOLD_USER_AGENT",
    "chEMBL_tools/1.0 (colabfold client)",
)
_MAX_RETRIES = int(os.getenv("COLABFOLD_MAX_RETRIES", "5"))
_BACKOFF_SECONDS = float(os.getenv("COLABFOLD_BACKOFF_SECONDS", "1.5"))
_SUBMIT_TIMEOUT = (
    float(os.getenv("COLABFOLD_CONNECT_TIMEOUT", "10")),
    float(os.getenv("COLABFOLD_SUBMIT_READ_TIMEOUT", "30")),
)
_POLL_TIMEOUT = (
    float(os.getenv("COLABFOLD_CONNECT_TIMEOUT", "10")),
    float(os.getenv("COLABFOLD_POLL_READ_TIMEOUT", "30")),
)
_DOWNLOAD_TIMEOUT = (
    float(os.getenv("COLABFOLD_CONNECT_TIMEOUT", "10")),
    float(os.getenv("COLABFOLD_DOWNLOAD_READ_TIMEOUT", "300")),
)

_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def _normalize_sequence(sequence: str) -> str:
    lines = [line.strip() for line in sequence.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Sequence is empty.")
    if any(line.startswith(">") for line in lines):
        lines = [line for line in lines if not line.startswith(">")]
    normalized = "".join(lines).replace(" ", "").upper()
    if not normalized:
        raise ValueError("No residues found in sequence input.")
    return normalized


def _request(
    method: str,
    url: str,
    on_retry: Callable[[str], None] | None = None,
    **kwargs,
) -> requests.Response:
    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, **kwargs)
            if resp.status_code in _RETRY_STATUS_CODES and attempt < _MAX_RETRIES:
                delay = _BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                if on_retry:
                    on_retry(
                        (
                            f"ColabFold request retry {attempt + 1}/{_MAX_RETRIES}: "
                            f"HTTP {resp.status_code}; retrying in {delay:.1f}s..."
                        )
                    )
                time.sleep(delay)
                continue
            return resp
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt >= _MAX_RETRIES:
                break
            delay = _BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
            if on_retry:
                on_retry(
                    (
                        f"ColabFold request retry {attempt + 1}/{_MAX_RETRIES}: "
                        f"{type(exc).__name__}; retrying in {delay:.1f}s..."
                    )
                )
            time.sleep(delay)

    raise RuntimeError(
        f"ColabFold API request failed after {_MAX_RETRIES + 1} attempts: {last_error}"
    )


def _request_with_fallback(
    method: str,
    path: str,
    on_retry: Callable[[str], None] | None = None,
    **kwargs,
) -> requests.Response:
    primary = f"{_BASE}{path}"
    try:
        return _request(method, primary, on_retry=on_retry, **kwargs)
    except RuntimeError as primary_error:
        fallback = f"{_FALLBACK_BASE}{path}"
        if fallback == primary:
            raise
        if on_retry:
            on_retry(
                "Primary ColabFold host failed after retries; trying fallback host..."
            )
        try:
            return _request(method, fallback, on_retry=on_retry, **kwargs)
        except RuntimeError as fallback_error:
            raise RuntimeError(
                "ColabFold request failed on primary and fallback hosts: "
                f"primary={primary_error}; fallback={fallback_error}"
            ) from fallback_error


def _submit_query(query: str, on_retry: Callable[[str], None] | None = None) -> dict:
    resp = _request_with_fallback(
        "POST",
        "/ticket/msa",
        data={"q": query, "mode": "env"},
        headers={"User-Agent": _USER_AGENT},
        timeout=_SUBMIT_TIMEOUT,
        on_retry=on_retry,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "id" not in payload:
        raise RuntimeError(f"ColabFold response missing job id: {payload}")
    return payload


def _sequence_from_query(query: str) -> str:
    lines = [line.strip() for line in query.splitlines() if line.strip()]
    seq_lines = [line for line in lines if not line.startswith(">")]
    return "".join(seq_lines)


def _write_single_sequence_a3m(query: str, output_path: str) -> str:
    seq = _sequence_from_query(query)
    if not seq:
        raise RuntimeError("Could not derive sequence for fallback A3M generation.")
    with open(output_path, "w", encoding="utf-8") as out:
        out.write(">query\n")
        out.write(f"{seq}\n")
    return output_path


def submit_msa_job(
    sequence: str, on_retry: Callable[[str], None] | None = None
) -> tuple[str, str, str]:
    normalized = _normalize_sequence(sequence)
    query = f">101\n{normalized}\n"
    payload = _submit_query(query, on_retry=on_retry)
    return payload["id"], payload.get("status", "UNKNOWN"), query


def poll_job(
    job_id: str,
    query: str,
    on_retry: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    # The newer ColabFold API can reject /ticket/{id} with 400 "invalid ID".
    # In that case, re-submitting the same query returns current status for that job hash.
    try:
        resp = _request_with_fallback(
            "GET",
            f"/ticket/{job_id}",
            headers={"User-Agent": _USER_AGENT},
            timeout=_POLL_TIMEOUT,
            on_retry=on_retry,
        )
        resp.raise_for_status()
        payload = resp.json()
        return payload.get("status", "UNKNOWN"), payload.get("id", job_id)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code not in (400, 404):
            raise

    payload = _submit_query(query, on_retry=on_retry)
    return payload.get("status", "UNKNOWN"), payload.get("id", job_id)


def download_msa(
    job_id: str,
    output_path: str,
    query: str | None = None,
    on_retry: Callable[[str], None] | None = None,
) -> tuple[str, bool]:
    resp = _request_with_fallback(
        "GET",
        f"/result/download/{job_id}",
        headers={"User-Agent": _USER_AGENT},
        timeout=_DOWNLOAD_TIMEOUT,
        stream=True,
        on_retry=on_retry,
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        if (
            query
            and exc.response is not None
            and exc.response.status_code == 400
            and "invalid ID" in exc.response.text
        ):
            return _write_single_sequence_a3m(query, output_path), True
        raise

    raw = io.BytesIO(resp.content)
    with tarfile.open(fileobj=raw, mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith(".a3m"):
                f = tar.extractfile(member)
                if f:
                    with open(output_path, "wb") as out:
                        out.write(f.read())
                    return output_path, False

    if query:
        return _write_single_sequence_a3m(query, output_path), True
    raise RuntimeError("No .a3m file found in ColabFold result archive")
