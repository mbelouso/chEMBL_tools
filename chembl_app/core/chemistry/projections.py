import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from sklearn.decomposition import PCA


def run_pca(fps_array: np.ndarray) -> np.ndarray:
    pca = PCA(n_components=2, random_state=42)
    return pca.fit_transform(fps_array)


def run_umap(fps_array: np.ndarray) -> np.ndarray:
    from umap import UMAP
    reducer = UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
    return reducer.fit_transform(fps_array)


def make_projection_figure(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    xlabel: str,
    ylabel: str,
    title: str,
    color_col: str = "cluster",
) -> Figure:
    fig, ax = plt.subplots(figsize=(7, 5))
    if color_col in df.columns:
        scatter = ax.scatter(
            df[x_col], df[y_col],
            c=df[color_col], cmap="tab20", alpha=0.6, s=18,
        )
        plt.colorbar(scatter, ax=ax, label=color_col)
    else:
        ax.scatter(df[x_col], df[y_col], alpha=0.6, s=18, color="steelblue")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    return fig
