import io
import tarfile
import requests


_BASE = "https://api.colabfold.com"


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


def _submit_query(query: str) -> dict:
    resp = requests.post(
        f"{_BASE}/ticket/msa",
        data={"q": query, "mode": "env"},
        headers={"User-Agent": "boltz"},
        timeout=30,
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


def submit_msa_job(sequence: str) -> tuple[str, str, str]:
    normalized = _normalize_sequence(sequence)
    query = f">101\n{normalized}\n"
    payload = _submit_query(query)
    return payload["id"], payload.get("status", "UNKNOWN"), query


def poll_job(job_id: str, query: str) -> tuple[str, str]:
    # The newer ColabFold API can reject /ticket/{id} with 400 "invalid ID".
    # In that case, re-submitting the same query returns current status for that job hash.
    try:
        resp = requests.get(f"{_BASE}/ticket/{job_id}", timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        return payload.get("status", "UNKNOWN"), payload.get("id", job_id)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code not in (400, 404):
            raise

    payload = _submit_query(query)
    return payload.get("status", "UNKNOWN"), payload.get("id", job_id)


def download_msa(job_id: str, output_path: str, query: str | None = None) -> tuple[str, bool]:
    resp = requests.get(f"{_BASE}/result/download/{job_id}", timeout=120, stream=True)
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
