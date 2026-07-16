import os
import re
import yaml
import pandas as pd
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class YAMLParams:
    mode: str               # "affinity" or "template"
    protein_sequence: str
    msa_path: str
    output_dir: str
    n_dirs: int = 4
    template_cif_path: str = ""
    chain_a: str = "A"
    chain_b: str = "B"


def _fix_yaml_quotes(contents: str) -> str:
    contents = re.sub(r"(smiles: )(.*)", r"\1'\2'", contents)
    contents = re.sub(r"'(\[A\])'", r"\1", contents)
    contents = re.sub(r"'(\[B\])'", r"\1", contents)
    contents = re.sub(r"'(\[R\])'", r"\1", contents)
    return contents


def generate_yaml_files(
    df: pd.DataFrame,
    params: YAMLParams,
    progress_cb: Optional[Callable[[int], None]] = None,
):
    os.makedirs(params.output_dir, exist_ok=True)
    n_dirs = params.n_dirs
    for i in range(1, n_dirs + 1):
        os.makedirs(os.path.join(params.output_dir, f"yaml{i}"), exist_ok=True)

    total = len(df)
    for idx, (_, row) in enumerate(df.iterrows()):
        molecule_name = str(row["chembl_id"]).replace(" ", "_")
        smiles = row["canonical_smiles"]

        msa_relpath = f"./{os.path.basename(params.msa_path)}" if params.msa_path else ""
        protein_entry = {
            "id": params.chain_a,
            "sequence": params.protein_sequence,
            "msa": msa_relpath,
        }
        ligand_entry = {"id": params.chain_b, "smiles": smiles}

        if params.mode == "template":
            output_data = {
                "version": 1,
                "sequences": [
                    {"protein": protein_entry},
                    {"ligand": ligand_entry},
                ],
                "templates": [{"cif": params.template_cif_path}],
            }
        else:
            output_data = {
                "version": 1,
                "sequences": [
                    {"protein": protein_entry},
                    {"ligand": ligand_entry},
                ],
                "properties": [{"affinity": {"binder": params.chain_b}}],
            }

        dir_index = (idx % n_dirs) + 1
        subdir = os.path.join(params.output_dir, f"yaml{dir_index}")
        filepath = os.path.join(subdir, f"{molecule_name}.yaml")

        with open(filepath, "w") as fh:
            yaml.dump(output_data, fh, default_flow_style=False, sort_keys=False)

        with open(filepath, "r") as fh:
            contents = fh.read()
        contents = _fix_yaml_quotes(contents)
        with open(filepath, "w") as fh:
            fh.write(contents)

        if progress_cb:
            progress_cb(int((idx + 1) / total * 100))
