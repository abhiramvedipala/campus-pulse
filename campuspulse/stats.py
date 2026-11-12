"""Small statistics helpers: seeded cluster bootstrap, residualised Spearman, effect sizes."""

import numpy as np
import pandas as pd
from scipy import stats

SEED = 20


def rng_for(name: str) -> np.random.Generator:
    """Deterministic generator per analysis name (stable across runs and machines)."""
    return np.random.default_rng(SEED + sum(map(ord, name)))


def unit_groups(unitid: pd.Series) -> list[np.ndarray]:
    codes, _ = pd.factorize(unitid)
    order = np.argsort(codes, kind="stable")
    cuts = np.flatnonzero(np.diff(codes[order])) + 1
    return np.split(order, cuts)


def cluster_boot(groups, stat, reps, rng) -> np.ndarray:
    """Resample whole units (institutions) with replacement; `stat(idx)` takes row indices."""
    u = len(groups)
    out = np.empty(reps)
    for b in range(reps):
        pick = rng.integers(0, u, u)
        out[b] = stat(np.concatenate([groups[i] for i in pick]))
    return out


def ci(boot: np.ndarray) -> tuple[float, float]:
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    return float(lo), float(hi)


def residualise(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta


def partial_spearman(x, y, X) -> float:
    """Spearman correlation of x and y after removing the linear effect of X from both (one lstsq call)."""
    beta, *_ = np.linalg.lstsq(X, np.column_stack([x, y]), rcond=None)
    r = np.column_stack([x, y]) - X @ beta
    return spearman(r[:, 0], r[:, 1])


def spearman(x, y) -> float:
    return float(stats.spearmanr(x, y).statistic)


def epsilon_squared(h: float, n: int) -> float:
    """Effect size for Kruskal-Wallis: H * (n + 1) / (n^2 - 1)."""
    return h * (n + 1) / (n**2 - 1)


def rank_biserial(a, b) -> float:
    """Positive when values in a tend to exceed values in b; range -1..1."""
    u = stats.mannwhitneyu(a, b, alternative="two-sided").statistic
    return float(2 * u / (len(a) * len(b)) - 1)
