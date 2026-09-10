from __future__ import annotations

import math


def is_prime(value: int) -> bool:
    if value < 2:
        return False
    if value in (2, 3):
        return True
    if value % 2 == 0:
        return False
    limit = int(math.isqrt(value))
    for candidate in range(3, limit + 1, 2):
        if value % candidate == 0:
            return False
    return True


def next_prime(value: int) -> int:
    candidate = max(2, value)
    while not is_prime(candidate):
        candidate += 1
    return candidate


def require_prime(value: int) -> int:
    if not is_prime(value):
        raise ValueError(f"Seed must be prime, got {value}.")
    return value
