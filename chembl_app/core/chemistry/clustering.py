import numpy as np
import pandas as pd
from dataclasses import dataclass
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, silhouette_score, davies_bouldin_score
from sklearn.mixture import GaussianMixture

try:
    import hdbscan
    _HDBSCAN_AVAILABLE = True
except ImportError:
    _HDBSCAN_AVAILABLE = False


@dataclass
class ClusterParams:
    algorithm: str = "kmeans"   # "kmeans" or "gmm"
    n_clusters: int = 20
    auto_k: bool = True
    auto_k_method: str = "ensemble"  # "ensemble", "calinski", "silhouette", "davies_bouldin", "hdbscan"
    k_min: int = 4
    k_max: int = 40
    selection_mode: str = "random_near_centroid"  # "random_near_centroid" or "tightness"
    random_per_cluster: int = 3
    centroid_quantile: float = 0.4
    random_seed: int = 42
    tightness_quantile: float = 0.30


def estimate_n_clusters(fps_array: np.ndarray, params: ClusterParams) -> int:
    n_samples = int(fps_array.shape[0])
    if n_samples < 3:
        return 1

    k_low = max(2, min(params.k_min, n_samples - 1))
    k_high = max(k_low, min(params.k_max, n_samples - 1))
    method = (params.auto_k_method or "ensemble").strip().lower()

    if method == "hdbscan":
        if not _HDBSCAN_AVAILABLE:
            method = "ensemble"
        else:
            min_cluster_size = max(5, min(50, n_samples // 25 if n_samples >= 25 else 3))
            labels = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size).fit_predict(fps_array)
            classes = sorted(c for c in np.unique(labels) if c >= 0)
            if len(classes) >= 2:
                return max(k_low, min(k_high, len(classes)))
            method = "ensemble"

    best_k = min(params.n_clusters, n_samples)
    ch_scores = {}
    sil_scores = {}
    db_scores = {}

    for k in range(k_low, k_high + 1):
        test_params = ClusterParams(
            algorithm=params.algorithm,
            n_clusters=k,
            auto_k=False,
            auto_k_method=params.auto_k_method,
            k_min=params.k_min,
            k_max=params.k_max,
            selection_mode=params.selection_mode,
            random_per_cluster=params.random_per_cluster,
            centroid_quantile=params.centroid_quantile,
            random_seed=params.random_seed,
            tightness_quantile=params.tightness_quantile,
        )
        try:
            labels, _ = cluster(fps_array, test_params)
            if len(np.unique(labels)) < 2:
                continue
            ch_scores[k] = float(calinski_harabasz_score(fps_array, labels))
            sil_scores[k] = float(silhouette_score(fps_array, labels))
            db_scores[k] = float(davies_bouldin_score(fps_array, labels))
        except Exception:
            continue

    if not ch_scores:
        return max(1, min(params.n_clusters, n_samples))

    valid_ks = sorted(ch_scores.keys())

    if method == "calinski":
        best_k = max(valid_ks, key=lambda k: ch_scores[k])
    elif method == "silhouette":
        best_k = max(valid_ks, key=lambda k: sil_scores[k])
    elif method == "davies_bouldin":
        best_k = min(valid_ks, key=lambda k: db_scores[k])
    else:
        ch_vals = np.array([ch_scores[k] for k in valid_ks], dtype=float)
        sil_vals = np.array([sil_scores[k] for k in valid_ks], dtype=float)
        db_vals = np.array([db_scores[k] for k in valid_ks], dtype=float)

        def _normalize(vals: np.ndarray) -> np.ndarray:
            lo = float(np.min(vals))
            hi = float(np.max(vals))
            if hi - lo < 1e-12:
                return np.ones_like(vals) * 0.5
            return (vals - lo) / (hi - lo)

        ch_n = _normalize(ch_vals)
        sil_n = _normalize(sil_vals)
        db_n = 1.0 - _normalize(db_vals)

        combined = 0.45 * sil_n + 0.35 * ch_n + 0.20 * db_n
        best_idx = int(np.argmax(combined))
        best_k = valid_ks[best_idx]

        if best_k in (k_low, k_high) and len(valid_ks) > 3:
            interior = [k for k in valid_ks if k not in (k_low, k_high)]
            if interior:
                best_interior = max(interior, key=lambda k: combined[valid_ks.index(k)])
                if combined[valid_ks.index(best_interior)] >= combined[best_idx] * 0.95:
                    best_k = best_interior

    return int(max(k_low, min(k_high, best_k)))


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


def random_select_near_centroid(
    df: pd.DataFrame,
    fps_array: np.ndarray,
    labels: np.ndarray,
    centers: np.ndarray,
    params: ClusterParams,
) -> pd.DataFrame:
    df_work = df.copy()
    df_work["cluster"] = labels

    picks = []
    unique_clusters = np.unique(labels)
    for cid in unique_clusters:
        mask = labels == cid
        sub = df_work[mask].copy()
        sub_fps = fps_array[mask]
        if sub.empty:
            continue

        dists = cdist([centers[int(cid)]], sub_fps, metric="euclidean")[0]
        sub["distance_to_center"] = dists

        quantile = float(np.clip(params.centroid_quantile, 0.05, 1.0))
        dist_threshold = np.quantile(dists, quantile)
        candidates = sub[sub["distance_to_center"] <= dist_threshold].copy()
        if candidates.empty:
            candidates = sub.nsmallest(1, "distance_to_center")

        n_pick = max(1, min(int(params.random_per_cluster), len(candidates)))
        rng = np.random.default_rng(int(params.random_seed) + int(cid))
        chosen_idx = rng.choice(candidates.index.to_numpy(), size=n_pick, replace=False)
        picks.append(candidates.loc[chosen_idx])

    if not picks:
        out = df_work.copy()
        out["distance_to_center"] = np.nan
        return out

    out = pd.concat(picks, ignore_index=True)
    return out.sort_values(["cluster", "distance_to_center"]).reset_index(drop=True)


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
