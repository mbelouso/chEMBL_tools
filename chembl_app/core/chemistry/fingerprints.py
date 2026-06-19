import numpy as np
import pandas as pd
from rdkit import DataStructs
from rdkit.Chem import AllChem, rdFingerprintGenerator
from tqdm import tqdm

try:
    from molbloom import buy as molbloom_buy
    _MOLBLOOM_AVAILABLE = True
except ImportError:
    _MOLBLOOM_AVAILABLE = False


def compute_fingerprints(df: pd.DataFrame) -> np.ndarray:
    mols = df["canonical_smiles"].apply(AllChem.MolFromSmiles)
    morgan_gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fps = []
    for mol in tqdm(mols, desc="Generating fingerprints", leave=False):
        if mol is not None:
            fp = morgan_gen.GetFingerprint(mol)
            arr = np.zeros((2048,), dtype=np.int8)
            DataStructs.ConvertToNumpyArray(fp, arr)
            fps.append(arr)
        else:
            fps.append(np.zeros(2048, dtype=np.int8))
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
