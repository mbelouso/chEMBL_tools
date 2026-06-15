import os


def read_fasta(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"FASTA file not found: {path}")
    seq_lines = []
    with open(path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(">"):
                continue
            seq_lines.append(line)
    return "".join(seq_lines)
