from dataclasses import dataclass, field
import pandas as pd
import numpy as np


@dataclass
class AppState:
    db_path: str = ""
    current_results: pd.DataFrame = field(default=None)
    fps_array: np.ndarray = field(default=None)
    tsne_coords: np.ndarray = field(default=None)
    diversity_results: pd.DataFrame = field(default=None)
    protein_sequence: str = ""
