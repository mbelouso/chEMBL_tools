import numpy as np
import pandas as pd
from dataclasses import dataclass
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.metrics import calinski_harabasz_score, silhouette_score, davies_bouldin_score
from sklearn.mixture import GaussianMixture

_ESTIMATION_SUBSAMPLE = 2000   # max compounds used during the k-sweep
_COARSE_STEP = 4               # step size for the coarse k-scan

try:
    import hdbscan
    _HDBSCAN_AVAILABLE = True
except ImportError:
    _HDBSCAN_AVAILABLE = False


@dataclass
class ClusterParams:
    algorithm: str = "kmeans"   # "kmeans", "gmm", or "butina"
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
    butina_distance_cutoff: float = 0.4  # Tanimoto distance cutoff for Butina


def _pick_best_k_from_scores(scores: dict, method: str) -> int:
    """Select best k from {k: {"ch": float, "db": float, "sil": float?}}."""
    valid_ks = sorted(scores.keys())

    if method == "calinski":
        return max(valid_ks, key=lambda k: scores[k]["ch"])
    if method == "davies_bouldin":
        return min(valid_ks, key=lambda k: scores[k]["db"])
    if method == "silhouette":
        return max(valid_ks, key=lambda k: scores[k].get("sil", 0.0))

    # Ensemble: CH (higher = better) + DB (lower = better), no silhouette in sweep
    ch_vals = np.array([scores[k]["ch"] for k in valid_ks], dtype=float)
    db_vals = np.array([scores[k]["db"] for k in valid_ks], dtype=float)

    def _norm(v: np.ndarray) -> np.ndarray:
        lo, hi = float(np.min(v)), float(np.max(v))
        return (v - lo) / (hi - lo) if hi - lo > 1e-12 else np.full_like(v, 0.5)

    combined = 0.55 * _norm(ch_vals) + 0.45 * (1.0 - _norm(db_vals))
    best_idx = int(np.argmax(combined))
    best_k = valid_ks[best_idx]

    # Prefer an interior k if the boundary winner is only marginally better
    if best_k in (valid_ks[0], valid_ks[-1]) and len(valid_ks) > 3:
        interior = [k for k in valid_ks if k not in (valid_ks[0], valid_ks[-1])]
        if interior:
            best_int = max(interior, key=lambda k: combined[valid_ks.index(k)])
            if combined[valid_ks.index(best_int)] >= combined[best_idx] * 0.95:
                best_k = best_int

    return int(best_k)


def estimate_n_clusters(fps_array: np.ndarray, params: ClusterParams) -> int:
    n_samples = int(fps_array.shape[0])
    if n_samples < 3:
        return 1

    k_low = max(2, min(params.k_min, n_samples - 1))
    k_high = max(k_low, min(params.k_max, n_samples - 1))
    method = (params.auto_k_method or "ensemble").strip().lower()

    # HDBSCAN: single fit on the full dataset, no sweep needed
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

    # Subsample for the k-sweep so cost stays low regardless of dataset size
    rng_seed = int(params.random_seed)
    rng = np.random.default_rng(rng_seed)
    if n_samples > _ESTIMATION_SUBSAMPLE:
        idx = rng.choice(n_samples, size=_ESTIMATION_SUBSAMPLE, replace=False)
        sub = fps_array[idx]
    else:
        sub = fps_array
    n_sub = len(sub)

    # Clamp k range to the subsample size
    k_lo = max(2, min(k_low, n_sub - 1))
    k_hi = max(k_lo, min(k_high, n_sub - 1))

    def _score_k(k: int) -> dict | None:
        batch = min(n_sub, max(k * 3, 256))
        km = MiniBatchKMeans(
            n_clusters=k, random_state=rng_seed,
            n_init=3, batch_size=batch, max_iter=100,
        )
        try:
            labels = km.fit_predict(sub)
        except Exception:
            return None
        if len(np.unique(labels)) < 2:
            return None
        entry = {
            "ch": float(calinski_harabasz_score(sub, labels)),
            "db": float(davies_bouldin_score(sub, labels)),
        }
        if method == "silhouette":
            samp = min(500, n_sub)
            entry["sil"] = float(silhouette_score(sub, labels, sample_size=samp, random_state=rng_seed))
        return entry

    # Coarse pass: scan every _COARSE_STEP to find the promising region
    coarse_ks = list(range(k_lo, k_hi + 1, _COARSE_STEP))
    if k_hi not in coarse_ks:
        coarse_ks.append(k_hi)

    all_scores: dict[int, dict] = {}
    for k in coarse_ks:
        s = _score_k(k)
        if s is not None:
            all_scores[k] = s

    if not all_scores:
        return max(1, min(params.n_clusters, n_samples))

    best_coarse = _pick_best_k_from_scores(all_scores, method)

    # Fine pass: fill in every integer within ±_COARSE_STEP of the coarse winner
    fine_lo = max(k_lo, best_coarse - _COARSE_STEP)
    fine_hi = min(k_hi, best_coarse + _COARSE_STEP)
    for k in range(fine_lo, fine_hi + 1):
        if k not in all_scores:
            s = _score_k(k)
            if s is not None:
                all_scores[k] = s

    best_k = _pick_best_k_from_scores(all_scores, method)
    return int(max(k_low, min(k_high, best_k)))


def _tanimoto_dist_lower_triangle(fps_array: np.ndarray) -> list:
    """Compute lower-triangle Tanimoto distance list for Butina."""
    n = len(fps_array)
    fp_f = fps_array.astype(np.float32)
    norms = np.sum(fp_f, axis=1)  # number of set bits per fingerprint
    dists = []
    for i in range(1, n):
        dots = fp_f[:i] @ fp_f[i]          # shape (i,)
        unions = norms[:i] + norms[i] - dots
        sims = np.where(unions > 0, dots / unions, 1.0)
        dists.extend((1.0 - sims).tolist())
    return dists


def cluster_butina(fps_array: np.ndarray, params: ClusterParams):
    from rdkit.ML.Cluster import Butina  # local import — only used when Butina is chosen

    n = len(fps_array)
    dists = _tanimoto_dist_lower_triangle(fps_array)
    raw_clusters = Butina.ClusterData(dists, n, float(params.butina_distance_cutoff), isDistData=True)

    labels = np.zeros(n, dtype=int)
    for cid, members in enumerate(raw_clusters):
        for mol_idx in members:
            labels[mol_idx] = cid

    # Cluster centers are the first (representative) member of each Butina cluster
    centers = np.array([fps_array[members[0]] for members in raw_clusters], dtype=float)
    return labels, centers


def cluster(fps_array: np.ndarray, params: ClusterParams):
    if params.algorithm == "butina":
        return cluster_butina(fps_array, params)
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
