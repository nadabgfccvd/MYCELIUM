"""Baseline: order-preserving dedupe, O(n^2) membership scan."""


def dedupe(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out
