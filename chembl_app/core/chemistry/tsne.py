import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.manifold import TSNE

from core.chemistry.projections import make_projection_figure


def run_tsne(fps_array: np.ndarray) -> np.ndarray:
    tsne = TSNE(n_components=2, random_state=42)
    return tsne.fit_transform(fps_array)


def make_tsne_figure(df: pd.DataFrame, color_col: str = "cluster") -> Figure:
    return make_projection_figure(
        df, "tsne_x", "tsne_y",
        "t-SNE 1", "t-SNE 2",
        f"t-SNE — {len(df)} compounds",
        color_col=color_col,
    )
