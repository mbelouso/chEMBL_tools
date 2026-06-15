import math
import pandas as pd
import sqlite3
from core.db.queries import query_export_details, pchembl_to_nm


def export_csv(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    output_path: str,
):
    molregnos = df["molregno"].tolist()
    details = query_export_details(conn, molregnos)

    base_cols = [
        "chembl_id", "canonical_smiles", "molecular_weight", "alogp",
        "hba", "hbd", "psa",
    ]
    export = df[[c for c in base_cols if c in df.columns]].copy()

    if not details.empty:
        details["best_nm"] = details["best_pchembl"].apply(
            lambda v: round(pchembl_to_nm(v), 3) if pd.notna(v) else None
        )
        for act_type in ("IC50", "EC50", "Ki"):
            sub = details[details["standard_type"] == act_type][
                ["molregno", "best_nm", "target_name", "target_chembl_id", "uniprot_accession", "assay_count"]
            ].copy()
            sub = sub.rename(columns={
                "best_nm": f"best_{act_type.lower()}_nm",
                "target_name": f"{act_type}_target_name",
                "target_chembl_id": f"{act_type}_target_chembl_id",
                "uniprot_accession": f"{act_type}_uniprot",
                "assay_count": f"{act_type}_assay_count",
            })
            # keep best (lowest nm = highest pchembl) per molregno
            sub = sub.groupby("molregno").first().reset_index()
            export = export.merge(
                sub.drop_duplicates("molregno"),
                left_on="molregno" if "molregno" in export.columns else None,
                right_on="molregno",
                how="left",
            ) if "molregno" in export.columns else export

    export.to_csv(output_path, index=False)
    return output_path
