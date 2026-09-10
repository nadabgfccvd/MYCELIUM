"""Variant: order-preserving dedupe with a seen-set, O(n) average."""


def dedupe(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
