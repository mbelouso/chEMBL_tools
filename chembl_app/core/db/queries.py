import math
import sqlite3
import pandas as pd
from typing import Tuple, Optional, Set


_PROPERTY_SQL = """
SELECT
    cs.molregno,
    cs.canonical_smiles,
    cp.mw_freebase  AS molecular_weight,
    cp.alogp,
    cp.hba,
    cp.hbd,
    cp.psa,
    cp.rtb,
    cp.num_ro5_violations,
    md.chembl_id
FROM compound_structures cs
JOIN compound_properties   cp ON cs.molregno = cp.molregno
JOIN molecule_dictionary   md ON cs.molregno = md.molregno
WHERE cp.mw_freebase BETWEEN ? AND ?
  AND cp.alogp       BETWEEN ? AND ?
  AND cs.canonical_smiles IS NOT NULL
"""

_TARGET_SQL = """
SELECT DISTINCT a.molregno
FROM activities        a
JOIN assays           asy ON a.assay_id = asy.assay_id
JOIN target_dictionary td  ON asy.tid   = td.tid
WHERE td.pref_name LIKE ?
  AND a.pchembl_value IS NOT NULL
"""

_ACTIVITY_SQL = """
SELECT molregno,
       MIN(pchembl_value) AS best_pchembl,
       COUNT(*)           AS assay_count
FROM activities
WHERE standard_type = ?
  AND pchembl_value IS NOT NULL
  AND molregno IN ({placeholders})
GROUP BY molregno
"""

_EXPORT_SQL = """
SELECT a.molregno,
       a.standard_type,
       MIN(a.pchembl_value)  AS best_pchembl,
    COUNT(*)              AS assay_count,
       td.pref_name          AS target_name,
       td.chembl_id          AS target_chembl_id,
       cs2.accession         AS uniprot_accession
FROM activities        a
JOIN assays           asy ON a.assay_id     = asy.assay_id
JOIN target_dictionary td  ON asy.tid       = td.tid
LEFT JOIN target_components  tc ON td.tid   = tc.tid
LEFT JOIN component_sequences cs2 ON tc.component_id = cs2.component_id
WHERE a.standard_type IN ('IC50','EC50','Ki')
  AND a.pchembl_value IS NOT NULL
  AND a.molregno IN ({placeholders})
GROUP BY a.molregno, a.standard_type, td.tid
ORDER BY a.molregno, best_pchembl DESC
"""


def query_by_properties(
    conn: sqlite3.Connection,
    mw_range: Tuple[float, float],
    logp_range: Tuple[float, float],
) -> pd.DataFrame:
    params = (mw_range[0], mw_range[1], logp_range[0], logp_range[1])
    return pd.read_sql_query(_PROPERTY_SQL, conn, params=params)


def query_target_molregnos(conn: sqlite3.Connection, target_text: str) -> Set[int]:
    cur = conn.execute(_TARGET_SQL, (f"%{target_text}%",))
    return {row[0] for row in cur.fetchall()}


def _chunked_in(molregnos, size=999):
    lst = list(molregnos)
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def query_activity_aggregates(
    conn: sqlite3.Connection,
    molregnos,
    standard_type: str,
) -> pd.DataFrame:
    chunks = []
    for chunk in _chunked_in(molregnos):
        ph = ",".join("?" * len(chunk))
        sql = _ACTIVITY_SQL.format(placeholders=ph)
        chunks.append(pd.read_sql_query(sql, conn, params=[standard_type] + chunk))
    if chunks:
        return pd.concat(chunks, ignore_index=True)
    return pd.DataFrame(columns=["molregno", "best_pchembl", "assay_count"])


def pchembl_to_nm(pchembl: float) -> float:
    return 10 ** (9 - pchembl)


def nm_to_pchembl(nm: float) -> float:
    return 9 - math.log10(nm)


def query_all_target_names(conn: sqlite3.Connection) -> list:
    cur = conn.execute(
        "SELECT DISTINCT pref_name FROM target_dictionary "
        "WHERE pref_name IS NOT NULL ORDER BY pref_name"
    )
    return [row[0] for row in cur.fetchall()]


def query_export_details(conn: sqlite3.Connection, molregnos) -> pd.DataFrame:
    chunks = []
    for chunk in _chunked_in(molregnos):
        ph = ",".join("?" * len(chunk))
        sql = _EXPORT_SQL.format(placeholders=ph)
        chunks.append(pd.read_sql_query(sql, conn, params=chunk))
    if chunks:
        return pd.concat(chunks, ignore_index=True)
    return pd.DataFrame()
