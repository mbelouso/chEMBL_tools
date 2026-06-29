import io
import tarfile
import requests


_BASE = "https://api.colabfold.com"


def submit_msa_job(sequence: str) -> str:
    query = f">101\n{sequence}\n"
    resp = requests.post(
        f"{_BASE}/ticket/msa",
        data={"q": query, "mode": "env"},
        headers={"User-Agent": "boltz"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def poll_job(job_id: str) -> str:
    resp = requests.get(f"{_BASE}/ticket/{job_id}", timeout=15)
    resp.raise_for_status()
    return resp.json().get("status", "UNKNOWN")


def download_msa(job_id: str, output_path: str) -> str:
    resp = requests.get(f"{_BASE}/result/download/{job_id}", timeout=120, stream=True)
    resp.raise_for_status()
    raw = io.BytesIO(resp.content)
    with tarfile.open(fileobj=raw, mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith(".a3m"):
                f = tar.extractfile(member)
                if f:
                    with open(output_path, "wb") as out:
                        out.write(f.read())
                    return output_path
    raise RuntimeError("No .a3m file found in ColabFold result archive")
