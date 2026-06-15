import numpy as np
import pandas as pd
from rdkit.Chem import AllChem
from tqdm import tqdm

try:
    from molbloom import buy as molbloom_buy
    _MOLBLOOM_AVAILABLE = True
except ImportError:
    _MOLBLOOM_AVAILABLE = False


def compute_fingerprints(df: pd.DataFrame) -> np.ndarray:
    mols = df["canonical_smiles"].apply(AllChem.MolFromSmiles)
    fps = []
    for mol in tqdm(mols, desc="Generating fingerprints", leave=False):
        if mol is not None:
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
            fps.append(np.array(fp))
        else:
            fps.append(np.zeros(2048, dtype=int))
    return np.array(fps)


def add_purchasability(df: pd.DataFrame) -> pd.DataFrame:
    if not _MOLBLOOM_AVAILABLE:
        df["purchasable"] = False
        return df
    df = df.copy()
    df["purchasable"] = [
        molbloom_buy(smi, canonicalize=True)
        for smi in tqdm(df["canonical_smiles"], desc="Checking purchasability", leave=False)
    ]
    return df
