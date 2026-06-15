import numpy as np
import pandas as pd
from dataclasses import dataclass
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture


@dataclass
class ClusterParams:
    algorithm: str = "kmeans"   # "kmeans" or "gmm"
    n_clusters: int = 20
    tightness_quantile: float = 0.30


def cluster(fps_array: np.ndarray, params: ClusterParams):
    if params.algorithm == "gmm":
        gmm = GaussianMixture(n_components=params.n_clusters, random_state=42, covariance_type="full")
        labels = gmm.fit_predict(fps_array)
        centers = gmm.means_
    else:
        km = KMeans(n_clusters=params.n_clusters, random_state=42, n_init=10)
        labels = km.fit_predict(fps_array)
        centers = km.cluster_centers_
    return labels, centers


def diversity_select(
    df: pd.DataFrame,
    fps_array: np.ndarray,
    labels: np.ndarray,
    centers: np.ndarray,
    params: ClusterParams,
) -> pd.DataFrame:
    n_clusters = params.n_clusters
    stats = []
    for cid in range(n_clusters):
        mask = labels == cid
        pts = fps_array[mask]
        if len(pts) < 2:
            continue
        dists = cdist([centers[cid]], pts, metric="euclidean")[0]
        stats.append({
            "cluster_id": cid,
            "size": len(pts),
            "mean_distance": np.mean(dists),
            "std_distance": np.std(dists),
            "tightness_score": np.mean(dists) + np.std(dists),
        })

    if not stats:
        df_out = df.copy()
        df_out["cluster"] = labels
        return df_out

    stats_df = pd.DataFrame(stats)
    threshold = stats_df["tightness_score"].quantile(params.tightness_quantile)
    tight_ids = set(stats_df.loc[stats_df["tightness_score"] <= threshold, "cluster_id"])

    df_work = df.copy()
    df_work["cluster"] = labels

    reps = []
    for cid in tight_ids:
        mask = labels == cid
        sub = df_work[mask].copy()
        sub_fps = fps_array[mask]
        dists = cdist([centers[cid]], sub_fps, metric="euclidean")[0]
        sub["distance_to_center"] = dists
        reps.append(sub.nsmallest(1, "distance_to_center"))

    non_tight = df_work[~df_work["cluster"].isin(tight_ids)].copy()
    parts = reps + [non_tight]
    return pd.concat(parts, ignore_index=True)
