"""Pure statistical primitives — pure Python, no numpy.

These are the foundation for forecasting, anomalies and scoring. Keep them
small, pure, and side-effect free so they remain trivially testable. If a
caller needs numpy later, the function signatures should not change.
"""
from __future__ import annotations
import math
from typing import Sequence


def mean(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def median(xs: Sequence[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def stdev(xs: Sequence[float]) -> float:
    """Population standard deviation. Returns 0.0 for sequences of length < 2."""
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / n)


def percentile(xs: Sequence[float], p: float) -> float:
    """Linear-interpolation percentile (p in 0..100)."""
    if not xs:
        return 0.0
    p = max(0.0, min(100.0, p))
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(s[int(k)])
    return s[f] + (s[c] - s[f]) * (k - f)


def z_score(value: float, m: float, sd: float) -> float:
    """Standard score. Returns 0.0 when sd is 0 (no variation in baseline)."""
    if sd <= 0:
        return 0.0
    return (value - m) / sd


def iqr_bounds(xs: Sequence[float], k: float = 1.5) -> tuple[float, float]:
    """Tukey fences: (lower, upper) past which a value is an outlier.
    k=1.5 → mild outlier, k=3.0 → extreme outlier."""
    if len(xs) < 4:
        return (0.0, 0.0)
    q1 = percentile(xs, 25)
    q3 = percentile(xs, 75)
    iqr = q3 - q1
    return (q1 - k * iqr, q3 + k * iqr)


def weighted_moving_average(xs: Sequence[float], weights: Sequence[float] | None = None) -> float:
    """Weighted average. Defaults to linear weights (older = lower weight)."""
    if not xs:
        return 0.0
    if weights is None:
        weights = list(range(1, len(xs) + 1))  # 1, 2, 3, ... newer last
    if len(weights) != len(xs):
        raise ValueError('weights and xs must have the same length')
    total_w = sum(weights)
    if total_w == 0:
        return mean(xs)
    return sum(x * w for x, w in zip(xs, weights)) / total_w


def linear_trend(xs: Sequence[float]) -> tuple[float, float]:
    """Simple least-squares regression on (index, value).
    Returns (slope, intercept). Slope > 0 → upward trend."""
    n = len(xs)
    if n < 2:
        return (0.0, float(xs[0]) if xs else 0.0)
    indices = list(range(n))
    mx = mean(indices)
    my = mean(xs)
    num = sum((indices[i] - mx) * (xs[i] - my) for i in range(n))
    den = sum((indices[i] - mx) ** 2 for i in range(n))
    if den == 0:
        return (0.0, my)
    slope = num / den
    intercept = my - slope * mx
    return (slope, intercept)


def safe_pct_change(current: float, baseline: float) -> float:
    """Percentage change with safe division. Returns 0.0 if baseline is 0."""
    if baseline == 0:
        return 0.0
    return ((current - baseline) / baseline) * 100.0
