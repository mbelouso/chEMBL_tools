import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from sklearn.decomposition import PCA


def run_pca(fps_array: np.ndarray) -> np.ndarray:
    pca = PCA(n_components=2, random_state=42)
    return pca.fit_transform(fps_array)


def run_umap(fps_array: np.ndarray) -> np.ndarray:
    try:
        from umap import UMAP
    except ImportError as exc:
        raise ImportError(
            "UMAP is not available. Install dependency 'umap-learn' "
            "(e.g., conda install -c conda-forge umap-learn)."
        ) from exc
    reducer = UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
    return reducer.fit_transform(fps_array)


def make_selection_overlay_figure(
    df_pre: pd.DataFrame,
    df_selected: pd.DataFrame,
    x_col: str = "tsne_x",
    y_col: str = "tsne_y",
    xlabel: str = "t-SNE 1",
    ylabel: str = "t-SNE 2",
    color_col: str = "cluster",
) -> Figure:
    """Plot all pre-filter compounds; unselected in grey, selected coloured by cluster."""
    fig = Figure(figsize=(7, 5))
    ax = fig.add_subplot(111)

    selected_ids = set(df_selected["molregno"].tolist()) if "molregno" in df_selected.columns else set()
    mask_sel = df_pre["molregno"].isin(selected_ids) if "molregno" in df_pre.columns else pd.Series([False] * len(df_pre))
    df_unsel = df_pre[~mask_sel]
    df_sel = df_pre[mask_sel]

    # Grey background: unselected
    ax.scatter(df_unsel[x_col], df_unsel[y_col], color="lightgrey", alpha=0.4, s=12, linewidths=0)

    # Coloured foreground: selected
    if not df_sel.empty:
        if color_col and color_col in df_sel.columns:
            scatter = ax.scatter(
                df_sel[x_col], df_sel[y_col],
                c=df_sel[color_col], cmap="tab20", alpha=0.8, s=22, linewidths=0,
            )
            fig.colorbar(scatter, ax=ax, label=color_col)
        else:
            ax.scatter(df_sel[x_col], df_sel[y_col], color="steelblue", alpha=0.8, s=22, linewidths=0)

    n_total = len(df_pre)
    n_sel = len(df_sel)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(f"Selection Overlay — {n_sel}/{n_total} kept (grey = removed)")
    fig.tight_layout()
    return fig


def make_projection_figure(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    xlabel: str,
    ylabel: str,
    title: str,
    color_col: str = "cluster",
) -> Figure:
    fig = Figure(figsize=(7, 5))
    ax = fig.add_subplot(111)
    if color_col in df.columns:
        scatter = ax.scatter(
            df[x_col], df[y_col],
            c=df[color_col], cmap="tab20", alpha=0.6, s=18,
        )
        fig.colorbar(scatter, ax=ax, label=color_col)
    else:
        ax.scatter(df[x_col], df[y_col], alpha=0.6, s=18, color="steelblue")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    return fig
