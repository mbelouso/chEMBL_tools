import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from sklearn.manifold import TSNE


def run_tsne(fps_array: np.ndarray) -> np.ndarray:
    tsne = TSNE(n_components=2, random_state=42)
    return tsne.fit_transform(fps_array)


def make_tsne_figure(df: pd.DataFrame, color_col: str = "cluster") -> Figure:
    fig, ax = plt.subplots(figsize=(7, 5))
    if color_col in df.columns:
        scatter = ax.scatter(
            df["tsne_x"], df["tsne_y"],
            c=df[color_col], cmap="tab20", alpha=0.6, s=18,
        )
        plt.colorbar(scatter, ax=ax, label=color_col)
    else:
        ax.scatter(df["tsne_x"], df["tsne_y"], alpha=0.6, s=18, color="steelblue")
    ax.set_xlabel("tSNE 1")
    ax.set_ylabel("tSNE 2")
    ax.set_title(f"tSNE — {len(df)} compounds")
    fig.tight_layout()
    return fig
