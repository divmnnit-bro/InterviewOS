"""Interval arithmetic on half-open [start, end) windows, in integer slots."""
from __future__ import annotations

Span = tuple[int, int]  # [start, end) in slot indices


def merge(spans: list[Span]) -> list[Span]:
    """Sort and merge overlapping or touching spans; drop empty ones."""
    out: list[Span] = []
    for s, e in sorted(x for x in spans if x[1] > x[0]):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def clip(spans: list[Span], lo: int, hi: int) -> list[Span]:
    return merge([(max(s, lo), min(e, hi)) for s, e in spans])


def subtract(spans: list[Span], busy: list[Span]) -> list[Span]:
    """Remove `busy` from `spans`. Both are merged first."""
    result: list[Span] = []
    busy = merge(busy)
    for s, e in merge(spans):
        cur = s
        for bs, be in busy:
            if be <= cur or bs >= e:
                continue
            if bs > cur:
                result.append((cur, bs))
            cur = max(cur, be)
            if cur >= e:
                break
        if cur < e:
            result.append((cur, e))
    return result


def start_spans(free: list[Span], duration: int) -> list[Span]:
    """Inclusive-start ranges [lo, hi] where a block of `duration` fits in `free`.

    Returned as half-open [lo, hi + 1) so they compose with the other helpers.
    """
    return [(s, e - duration + 1) for s, e in free if e - s >= duration]


def intersect(a: list[Span], b: list[Span]) -> list[Span]:
    out: list[Span] = []
    i = j = 0
    a, b = merge(a), merge(b)
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out
